
"""
services/cart.py — mirrors internal/services/cart.go
Cart is stored in Redis as JSON with a 2-hour TTL.
Uses an asyncio.Lock per session to prevent race conditions on concurrent
add calls — same intent as Go's sync.Mutex.
"""

import asyncio
import json
import logging
from datetime import timedelta

import redis.asyncio as aioredis

from models import Cart, CartItem
from services.catalog import CatalogService

log = logging.getLogger(__name__)

_CART_TTL = timedelta(hours=2)


class CartService:
    def __init__(self, rdb: aioredis.Redis, catalog: CatalogService) -> None:
        self.redis = rdb
        self.catalog = catalog
        self._locks: dict[str, asyncio.Lock] = {}

    def _key(self, session_id: str) -> str:
        return f"cart:{session_id}"

    def _lock(self, session_id: str) -> asyncio.Lock:
        if session_id not in self._locks:
            self._locks[session_id] = asyncio.Lock()
        return self._locks[session_id]

    async def get(self, session_id: str) -> Cart:
        raw = await self.redis.get(self._key(session_id))

        if raw is None:
            return Cart(session_id=session_id, items=[])

        data = json.loads(raw)
        return Cart.model_validate(data)

    async def _save(self, cart: Cart) -> None:
        await self.redis.set(
            self._key(cart.session_id),
            cart.model_dump_json(),
            ex=int(_CART_TTL.total_seconds()),
        )

    async def add_item(
        self,
        session_id: str,
        product_id: str,
        qty: int,
        reasoning: str = "",
    ) -> Cart:
        async with self._lock(session_id):
            product = await self.catalog.get_by_id(product_id)

            if product is None:
                raise ValueError("product not found")

            cart = await self.get(session_id)

            existing_qty = next(
                (
                    item.quantity
                    for item in cart.items
                    if item.product_id == product_id
                ),
                0,
            )

            if product.stock < existing_qty + qty:
                raise ValueError("STOCK_UNAVAILABLE")

            found = False

            for item in cart.items:
                if item.product_id == product_id:
                    item.quantity += qty
                    found = True
                    break

            if not found:
                cart.items.append(
                    CartItem(
                        product_id=product.id,
                        name=product.name,
                        price_paise=product.price_paise,
                        price_inr=product.price_inr,
                        quantity=qty,
                        reasoning=reasoning,
                        image_url=product.image_url,
                    )
                )

            cart.total_paise = sum(
                item.price_paise * item.quantity
                for item in cart.items
            )
            cart.total_inr = cart.total_paise / 100

            await self._save(cart)
            return cart

    async def remove_item(
        self,
        session_id: str,
        product_id: str,
        quantity_to_remove: int = 1,
    ) -> Cart:
        if quantity_to_remove < 1:
            raise ValueError("quantity_to_remove must be at least 1")

        async with self._lock(session_id):
            cart = await self.get(session_id)
            new_items: list[CartItem] = []
            found = False

            for item in cart.items:
                if item.product_id == product_id:
                    found = True
                    item.quantity -= quantity_to_remove

                    if item.quantity > 0:
                        new_items.append(item)
                else:
                    new_items.append(item)

            if not found:
                raise ValueError("product not found in cart")

            cart.items = new_items

            cart.total_paise = sum(
                item.price_paise * item.quantity
                for item in cart.items
            )
            cart.total_inr = cart.total_paise / 100

            await self._save(cart)
            return cart
