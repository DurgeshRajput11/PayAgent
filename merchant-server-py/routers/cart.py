"""
routers/cart.py — mirrors internal/handlers/cart.go
GET    /api/v1/cart/{session_id}
POST   /api/v1/cart/{session_id}/add
DELETE /api/v1/cart/{session_id}/remove/{product_id}
"""
from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel, Field

from models import AuditLog
from services.audit import AuditService
from services.cart import CartService

router = APIRouter(prefix="/api/v1/cart", tags=["cart"])


class AddItemRequest(BaseModel):
    product_id:      str = Field(..., min_length=1)
    quantity:        int = Field(..., ge=1)
    agent_reasoning: str = ""


@router.get("/{session_id}")
async def get_cart(session_id: str, request: Request):
    cart_svc: CartService = request.app.state.cart_svc
    cart = await cart_svc.get(session_id)
    return cart.model_dump(mode="json")


@router.post("/{session_id}/add")
async def add_item(session_id: str, body: AddItemRequest, request: Request):
    cart_svc:  CartService  = request.app.state.cart_svc
    audit_svc: AuditService = request.app.state.audit_svc

    try:
        cart = await cart_svc.add_item(
            session_id,
            body.product_id,
            body.quantity,
            body.agent_reasoning,
        )
    except ValueError as exc:
        err = str(exc)
        if err == "STOCK_UNAVAILABLE":
            # 409 Conflict — mirrors Go's differentiated stock error response
            raise HTTPException(
                status_code=409,
                detail={"error": "STOCK_UNAVAILABLE", "message": "Product out of stock"},
            )
        raise HTTPException(status_code=500, detail=err)

    await audit_svc.write(AuditLog(
        session_id=session_id,
        event_type="CART_ADD",
        actor="agent",
        reasoning=body.agent_reasoning,
        outcome="success",
    ))

    return {"cart": cart.model_dump(mode="json")}


@router.delete("/{session_id}/remove/{product_id}")
async def remove_item(
    session_id: str,
    product_id: str,
    request: Request,
    qty: int = Query(default=1, ge=1),
):
    cart_svc:  CartService  = request.app.state.cart_svc
    audit_svc: AuditService = request.app.state.audit_svc

    try:
        cart = await cart_svc.remove_item(session_id, product_id, qty)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

    await audit_svc.write(AuditLog(
        session_id=session_id,
        event_type="CART_REMOVE",
        actor="agent",
        outcome="success",
    ))

    return {"cart": cart.model_dump(mode="json")}