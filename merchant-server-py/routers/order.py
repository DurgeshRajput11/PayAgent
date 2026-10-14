"""
routers/order.py — mirrors internal/handlers/order.go

POST /api/v1/orders                     → Create
POST /api/v1/orders/{order_id}/confirm  → Confirm

Key invariants preserved from Go:
- amount_paise must equal sum(items[i].price_paise * quantity)
- Confirm requires all 3 Razorpay fields + valid HMAC signature
- Stock decrement + status update happen in a single DB transaction
- Idempotent: confirming an already-paid order returns success immediately
- Concurrent confirms can't both succeed against insufficient stock (FOR UPDATE)
"""
import json
from uuid import UUID

import asyncpg
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from models import AuditLog, CartItem
from services.audit import AuditService
from services.payment import PaymentService

router = APIRouter(prefix="/api/v1/orders", tags=["orders"])


class CreateOrderRequest(BaseModel):
    session_id:        str            = Field(..., min_length=1)
    razorpay_order_id: str            = Field(..., min_length=1)
    amount_paise:      int            = Field(..., gt=0)
    items:             list[CartItem] = Field(..., min_length=1)


class ConfirmOrderRequest(BaseModel):
    razorpay_payment_id: str = Field(..., min_length=1)
    razorpay_order_id:   str = Field(..., min_length=1)
    razorpay_signature:  str = Field(..., min_length=1)


@router.post("")
async def create_order(body: CreateOrderRequest, request: Request):
    pool:      asyncpg.Pool  = request.app.state.pool
    audit_svc: AuditService  = request.app.state.audit_svc

    # Invariant: amount_paise must equal sum of items (mirrors Go check)
    items_total = sum(item.price_paise * item.quantity for item in body.items)
    if items_total != body.amount_paise:
        raise HTTPException(
            status_code=400,
            detail={"error": "AMOUNT_MISMATCH", "message": "amount_paise does not match the sum of items"},
        )

    items_json = json.dumps([item.model_dump(mode="json") for item in body.items])

    try:
        row = await pool.fetchrow(
            """
            INSERT INTO orders (session_id, razorpay_order_id, amount_paise, items, status)
            VALUES ($1, $2, $3, $4::jsonb, 'pending')
            RETURNING id
            """,
            body.session_id,
            body.razorpay_order_id,
            body.amount_paise,
            items_json,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail={"error": "Failed to create order", "details": str(exc)})

    order_id = str(row["id"])

    await audit_svc.write(AuditLog(
        session_id=body.session_id,
        event_type="ORDER_CREATED",
        actor="system",
        reasoning="Order created successfully for Razorpay payment",
        outcome="success",
        payload={
            "razorpay_order_id": body.razorpay_order_id,
            "id":                order_id,
            "amount_paise":      body.amount_paise,
        },
    ))

    return {"id": order_id, "razorpay_order_id": body.razorpay_order_id, "status": "pending"}


@router.post("/{order_id}/confirm")
async def confirm_order(order_id: str, body: ConfirmOrderRequest, request: Request):
    pool:        asyncpg.Pool   = request.app.state.pool
    audit_svc:   AuditService   = request.app.state.audit_svc
    payment_svc: PaymentService = request.app.state.payment_svc

    # Verify Razorpay HMAC signature before touching the DB
    if not payment_svc.verify_signature(
        body.razorpay_order_id,
        body.razorpay_payment_id,
        body.razorpay_signature,
    ):
        raise HTTPException(
            status_code=401,
            detail={"error": "SIGNATURE_INVALID", "message": "Could not verify this payment with Razorpay"},
        )

    async with pool.acquire() as conn:
        async with conn.transaction():
            # Lock row for update — prevents duplicate confirms (mirrors Go FOR UPDATE)
            row = await conn.fetchrow(
                """
                SELECT session_id, status, items::text
                FROM orders
                WHERE id = $1 AND razorpay_order_id = $2
                FOR UPDATE
                """,
                order_id,
                body.razorpay_order_id,
            )

            if row is None:
                raise HTTPException(status_code=404, detail={"error": "ORDER_NOT_FOUND"})

            session_id = row["session_id"]
            status     = row["status"]

            # Idempotent: already-paid → return immediately without re-decrementing stock
            if status == "paid":
                return {"status": "paid"}

            items: list[CartItem] = [CartItem(**i) for i in json.loads(row["items"])]

            # Decrement stock inside the same transaction
            for item in items:
                tag = await conn.execute(
                    """
                    UPDATE products
                    SET stock = stock - $1, updated_at = NOW()
                    WHERE id = $2 AND stock >= $1
                    """,
                    item.quantity,
                    item.product_id,
                )
                # asyncpg returns "UPDATE N" — extract the row count
                rows_affected = int(tag.split()[-1])
                if rows_affected == 0:
                    await audit_svc.write(AuditLog(
                        session_id=session_id,
                        event_type="ORDER_CONFIRM_FAILED",
                        actor="system",
                        reasoning=f"Insufficient stock for {item.name} at payment confirmation",
                        outcome="failed",
                    ))
                    raise HTTPException(
                        status_code=409,
                        detail={
                            "error": "STOCK_UNAVAILABLE",
                            "message": "An item sold out before payment was confirmed; contact support for a refund",
                        },
                    )

            await conn.execute(
                "UPDATE orders SET status = 'paid' WHERE id = $1",
                order_id,
            )

    await audit_svc.write(AuditLog(
        session_id=session_id,
        event_type="ORDER_CONFIRMED",
        actor="user",
        reasoning="Payment verified via Razorpay signature and confirmed",
        outcome="success",
    ))

    return {"status": "paid"}