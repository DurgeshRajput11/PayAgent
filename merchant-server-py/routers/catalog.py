"""
routers/catalog.py — mirrors internal/handlers/catalog.go
GET /api/v1/catalog/search  → CatalogHandler.Search
GET /api/v1/catalog/{id}    → CatalogHandler.GetByID
"""
from fastapi import APIRouter, HTTPException, Query, Request

from models import AuditLog
from services.audit import AuditService
from services.catalog import CatalogService

router = APIRouter(prefix="/api/v1/catalog", tags=["catalog"])


@router.get("/search")
async def search(
    request: Request,
    q:             str   = Query(default=""),
    category:      str   = Query(default=""),
    max_price_inr: float = Query(default=0),
):
    catalog_svc: CatalogService = request.app.state.catalog_svc
    audit_svc:   AuditService   = request.app.state.audit_svc

    # Convert INR → paise for accurate monetary comparisons (mirrors Go handler)
    max_price_paise = int(max_price_inr * 100)

    products = await catalog_svc.search(q, category, max_price_paise)

    await audit_svc.write(AuditLog(
        session_id=request.headers.get("X-Session-ID", ""),
        event_type="CATALOG_SEARCH",
        actor="agent",
        reasoning=f"Searched catalog for: {q}",
        outcome="success",
    ))

    return {"products": [p.model_dump(mode="json") for p in products], "total": len(products)}


@router.get("/{product_id}")
async def get_by_id(product_id: str, request: Request):
    catalog_svc: CatalogService = request.app.state.catalog_svc

    if not product_id:
        raise HTTPException(status_code=400, detail="product_id is required")

    product = await catalog_svc.get_by_id(product_id)
    if product is None:
        raise HTTPException(status_code=404, detail="product not found")

    return product.model_dump(mode="json")