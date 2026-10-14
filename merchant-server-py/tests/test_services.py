"""
tests/test_services.py
Unit tests for CartService, CatalogService, PaymentService.
All DB/Redis calls are mocked — no real infrastructure needed.
"""
import asyncio
import json
import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

from models import Cart, CartItem, Product


# ── Helpers ──────────────────────────────────────────────────────────────────

def make_product(
    product_id: str = "prod-1",
    name: str       = "Test Product",
    price_paise: int = 100000,
    stock: int       = 10,
) -> Product:
    return Product(
        id=product_id,
        name=name,
        description="A product",
        category="electronics",
        price_paise=price_paise,
        price_inr=price_paise / 100,
        stock=stock,
        tags=["test"],
        image_url="",
        created_at=datetime.now(timezone.utc),
    )


# ── CartService ───────────────────────────────────────────────────────────────

class TestCartService:
    @pytest.fixture
    def cart_svc(self):
        from services.cart import CartService
        from services.catalog import CatalogService

        rdb     = AsyncMock()
        catalog = AsyncMock(spec=CatalogService)
        svc     = CartService(rdb, catalog)
        return svc, rdb, catalog

    @pytest.mark.asyncio
    async def test_get_empty_cart(self, cart_svc):
        svc, rdb, _ = cart_svc
        rdb.get.return_value = None   # Redis miss

        cart = await svc.get("session-1")
        assert cart.session_id == "session-1"
        assert cart.items == []
        assert cart.total_paise == 0

    @pytest.mark.asyncio
    async def test_get_existing_cart(self, cart_svc):
        svc, rdb, _ = cart_svc
        cart_data = Cart(
            session_id="session-1",
            items=[CartItem(product_id="p1", name="X", price_paise=1000, price_inr=10, quantity=2)],
            total_paise=2000,
            total_inr=20.0,
        )
        rdb.get.return_value = cart_data.model_dump_json()

        cart = await svc.get("session-1")
        assert len(cart.items) == 1
        assert cart.total_paise == 2000

    @pytest.mark.asyncio
    async def test_add_item_new(self, cart_svc):
        svc, rdb, catalog = cart_svc
        rdb.get.return_value  = None   # empty cart
        rdb.set.return_value  = True
        catalog.get_by_id.return_value = make_product("p1", price_paise=50000, stock=5)

        cart = await svc.add_item("session-1", "p1", 2, "good price")
        assert len(cart.items) == 1
        assert cart.items[0].quantity == 2
        assert cart.total_paise == 100000
        assert cart.total_inr == pytest.approx(1000.0)

    @pytest.mark.asyncio
    async def test_add_item_increments_existing(self, cart_svc):
        svc, rdb, catalog = cart_svc
        existing = Cart(
            session_id="s1",
            items=[CartItem(product_id="p1", name="X", price_paise=50000, price_inr=500, quantity=1)],
            total_paise=50000,
            total_inr=500.0,
        )
        rdb.get.return_value  = existing.model_dump_json()
        rdb.set.return_value  = True
        catalog.get_by_id.return_value = make_product("p1", price_paise=50000, stock=5)

        cart = await svc.add_item("s1", "p1", 2, "")
        assert cart.items[0].quantity == 3
        assert cart.total_paise == 150000

    @pytest.mark.asyncio
    async def test_add_item_stock_unavailable(self, cart_svc):
        svc, rdb, catalog = cart_svc
        rdb.get.return_value  = None
        catalog.get_by_id.return_value = make_product("p1", stock=1)

        with pytest.raises(ValueError, match="STOCK_UNAVAILABLE"):
            await svc.add_item("s1", "p1", 5, "")

    @pytest.mark.asyncio
    async def test_add_item_stock_check_includes_cart_quantity(self, cart_svc):
        """
        Stock=3, cart already has 2 → adding 2 more should fail.
        This mirrors the Go fix for double-add stock bypass.
        """
        svc, rdb, catalog = cart_svc
        existing = Cart(
            session_id="s1",
            items=[CartItem(product_id="p1", name="X", price_paise=1000, price_inr=10, quantity=2)],
            total_paise=2000,
            total_inr=20.0,
        )
        rdb.get.return_value  = existing.model_dump_json()
        catalog.get_by_id.return_value = make_product("p1", stock=3)

        with pytest.raises(ValueError, match="STOCK_UNAVAILABLE"):
            await svc.add_item("s1", "p1", 2, "")

    @pytest.mark.asyncio
    async def test_remove_item_full(self, cart_svc):
        svc, rdb, catalog = cart_svc
        existing = Cart(
            session_id="s1",
            items=[
                CartItem(product_id="p1", name="X", price_paise=1000, price_inr=10, quantity=3),
                CartItem(product_id="p2", name="Y", price_paise=2000, price_inr=20, quantity=1),
            ],
            total_paise=5000,
            total_inr=50.0,
        )
        rdb.get.return_value = existing.model_dump_json()
        rdb.set.return_value = True

        cart = await svc.remove_item("s1", "p1", 0)  # qty=0 → full removal
        assert len(cart.items) == 1
        assert cart.items[0].product_id == "p2"
        assert cart.total_paise == 2000

    @pytest.mark.asyncio
    async def test_remove_item_partial(self, cart_svc):
        svc, rdb, catalog = cart_svc
        existing = Cart(
            session_id="s1",
            items=[CartItem(product_id="p1", name="X", price_paise=1000, price_inr=10, quantity=5)],
            total_paise=5000,
            total_inr=50.0,
        )
        rdb.get.return_value = existing.model_dump_json()
        rdb.set.return_value = True

        cart = await svc.remove_item("s1", "p1", 2)
        assert cart.items[0].quantity == 3
        assert cart.total_paise == 3000


# ── CatalogService ────────────────────────────────────────────────────────────

class TestCatalogService:
    """
    Catalog service builds dynamic SQL — test the query-building logic
    by mocking pool.fetch and verifying the SQL contains the right clauses.
    """

    @pytest.fixture
    def catalog_svc(self):
        from services.catalog import CatalogService
        pool = AsyncMock()
        svc  = CatalogService(pool)
        return svc, pool

    @pytest.mark.asyncio
    async def test_search_no_filters(self, catalog_svc):
        svc, pool = catalog_svc
        pool.fetch.return_value = []
        result = await svc.search()
        assert result == []
        call_args = pool.fetch.call_args
        sql = call_args[0][0]
        assert "ORDER BY price_paise ASC LIMIT 20" in sql

    @pytest.mark.asyncio
    async def test_search_with_query(self, catalog_svc):
        svc, pool = catalog_svc
        pool.fetch.return_value = []
        await svc.search(query="mouse")
        sql  = pool.fetch.call_args[0][0]
        args = pool.fetch.call_args[0][1:]
        assert "ILIKE" in sql
        assert "%mouse%" in args

    @pytest.mark.asyncio
    async def test_search_with_category(self, catalog_svc):
        svc, pool = catalog_svc
        pool.fetch.return_value = []
        await svc.search(category="electronics")
        sql  = pool.fetch.call_args[0][0]
        args = pool.fetch.call_args[0][1:]
        assert "category = $" in sql
        assert "electronics" in args

    @pytest.mark.asyncio
    async def test_search_with_max_price(self, catalog_svc):
        svc, pool = catalog_svc
        pool.fetch.return_value = []
        await svc.search(max_price_paise=50000)
        sql  = pool.fetch.call_args[0][0]
        args = pool.fetch.call_args[0][1:]
        assert "price_paise <= $" in sql
        assert 50000 in args

    @pytest.mark.asyncio
    async def test_get_by_id_not_found(self, catalog_svc):
        svc, pool = catalog_svc
        pool.fetchrow.return_value = None
        result = await svc.get_by_id("nonexistent")
        assert result is None


# ── PaymentService ────────────────────────────────────────────────────────────

class TestPaymentService:
    def test_signature_verified_correctly(self):
        import hashlib, hmac as _hmac
        from services.payment import PaymentService

        secret   = "super_secret"
        order_id = "order_123"
        pay_id   = "pay_456"
        expected = _hmac.new(
            secret.encode(), f"{order_id}|{pay_id}".encode(), hashlib.sha256
        ).hexdigest()

        svc = PaymentService(secret)
        assert svc.verify_signature(order_id, pay_id, expected) is True

    def test_wrong_signature_rejected(self):
        from services.payment import PaymentService
        svc = PaymentService("secret")
        assert svc.verify_signature("o", "p", "wrong") is False

    def test_empty_secret_always_false(self):
        from services.payment import PaymentService
        svc = PaymentService("")
        assert svc.verify_signature("o", "p", "sig") is False