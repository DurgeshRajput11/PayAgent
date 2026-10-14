"""
models.py — Python equivalents of all Go models in internal/models/
Uses Pydantic v2 for validation and JSON serialisation.
"""
from __future__ import annotations
from datetime import datetime
from typing import Any, Optional
from pydantic import BaseModel


# ── Product (models/product.go) ──────────────────────────────────────────────
class Product(BaseModel):
    id:          str
    name:        str
    description: str        = ""
    category:    str        = ""
    price_paise: int
    price_inr:   float
    stock:       int
    tags:        list[str]  = []
    image_url:   str        = ""
    created_at:  datetime


# ── Cart (models/cart.go) ────────────────────────────────────────────────────
class CartItem(BaseModel):
    product_id:  str
    name:        str
    price_paise: int
    price_inr:   float
    quantity:    int
    reasoning:   str = ""
    image_url:   str = ""


class Cart(BaseModel):
    session_id:  str
    items:       list[CartItem] = []
    total_paise: int            = 0
    total_inr:   float          = 0.0


# ── AuditLog (models/audit.go) ───────────────────────────────────────────────
class AuditLog(BaseModel):
    id:         Optional[int]    = None
    session_id: str
    event_type: str
    actor:      str
    payload:    Optional[Any]    = None
    reasoning:  str              = ""
    outcome:    str              = ""
    created_at: Optional[datetime] = None


# ── UPIMandate (models/mandate.go) ───────────────────────────────────────────
class UPIMandate(BaseModel):
    id:               str
    session_id:       str
    customer_id:      str = ""
    token_id:         str = ""
    block_order_id:   str = ""
    max_amount_paise: int = 1_000_000
    status:           str = "pending"
    created_at:       datetime