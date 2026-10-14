"""
tests/test_routes.py
Integration tests for all HTTP routes.
Mocks DB/Redis — tests the full request/response cycle including middleware.
"""
import json
import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch, PropertyMock
from fastapi import FastAPI
from fastapi.testclient import TestClient

from models import AuditLog, Cart, CartItem, Product
from middleware import AgentAuthMiddleware, CORSMiddleware, RateLimitMiddleware
from routers import audit, analytics, cart, catalog, order, resume, stream

API_KEY = "test-key"
HEADERS = {"X-API-Key": API_KEY}


def make_test_app() -> FastAPI:
    """
    Build a FastAPI app with all routers and middleware, using mocked services
    injected onto app.state.
    """
    app = FastAPI()
    app.add_middleware(CORSMiddleware)
    app.add_middleware(AgentAuthMiddleware, api_key=API_KEY)

    # Inject mocked services
    app.state.pool        = AsyncMock()
    app.state.redis       = AsyncMock()
    app.state.audit_svc   = AsyncMock()
    app.state.catalog_svc = AsyncMock()
    app.state.cart_svc    = AsyncMock()
    app.state.payment_svc = MagicMock()

    @app.get("/health")
    def health():
        return {"status": "ok"}

    app.include_router(catalog.router)
    app.include_router(cart.router)
    app.include_router(audit.router)
    app.include_router(order.router)
    app.include_router(stream.router)
    app.include_router(resume.router)
    app.include_router(analytics.router)

    return app


def make_product(**kwargs) -> Product:
    defaults = dict(
        id="prod-1", name="Test Product", description="Desc",
        category="electronics", price_paise=100000, price_inr=1000.0,
        stock=10, tags=["test"], image_url="", created_at=datetime.now(timezone.utc),
    )
    defaults.update(kwargs)
    return Product(**defaults)


# ── Health ────────────────────────────────────────────────────────────────────

class TestHealth:
    def test_health_no_auth(self):
        client = TestClient(make_test_app())
        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.json() == {"status": "ok"}


# ── Catalog ───────────────────────────────────────────────────────────────────

class TestCatalog:
    @pytest.fixture
    def client(self):
        app = make_test_app()
        app.state.catalog_svc.search     = AsyncMock(return_value=[make_product()])
        app.state.catalog_svc.get_by_id  = AsyncMock(return_value=make_product())
        app.state.audit_svc.write        = AsyncMock()
        return TestClient(app)

    def test_search_requires_auth(self, client):
        resp = client.get("/api/v1/catalog/search")
        assert resp.status_code == 401

    def test_search_returns_products(self, client):
        resp = client.get("/api/v1/catalog/search?q=test", headers=HEADERS)
        assert resp.status_code == 200
        data = resp.json()
        assert "products" in data
        assert data["total"] == 1

    def test_search_with_max_price(self, client):
        resp = client.get("/api/v1/catalog/search?max_price_inr=500", headers=HEADERS)
        assert resp.status_code == 200

    def test_get_by_id_returns_product(self, client):
        resp = client.get("/api/v1/catalog/prod-1", headers=HEADERS)
        assert resp.status_code == 200
        assert resp.json()["id"] == "prod-1"

    def test_get_by_id_not_found(self, client):
        app = make_test_app()
        app.state.catalog_svc.get_by_id = AsyncMock(return_value=None)
        app.state.audit_svc.write       = AsyncMock()
        c = TestClient(app)
        resp = c.get("/api/v1/catalog/nonexistent", headers=HEADERS)
        assert resp.status_code == 404


# ── Cart ──────────────────────────────────────────────────────────────────────

class TestCart:
    @pytest.fixture
    def client(self):
        app = make_test_app()
        empty_cart = Cart(session_id="sess-1", items=[], total_paise=0, total_inr=0)
        app.state.cart_svc.get        = AsyncMock(return_value=empty_cart)
        app.state.cart_svc.add_item   = AsyncMock(return_value=Cart(
            session_id="sess-1",
            items=[CartItem(product_id="p1", name="X", price_paise=1000, price_inr=10, quantity=1)],
            total_paise=1000, total_inr=10.0,
        ))
        app.state.cart_svc.remove_item = AsyncMock(return_value=empty_cart)
        app.state.audit_svc.write      = AsyncMock()
        return TestClient(app)

    def test_get_cart(self, client):
        resp = client.get("/api/v1/cart/sess-1", headers=HEADERS)
        assert resp.status_code == 200
        assert resp.json()["session_id"] == "sess-1"

    def test_add_item(self, client):
        resp = client.post(
            "/api/v1/cart/sess-1/add",
            headers=HEADERS,
            json={"product_id": "p1", "quantity": 1, "agent_reasoning": "cheapest"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "cart" in data

    def test_add_item_missing_fields(self, client):
        resp = client.post(
            "/api/v1/cart/sess-1/add",
            headers=HEADERS,
            json={"quantity": 1},  # missing product_id
        )
        assert resp.status_code == 422

    def test_add_item_stock_unavailable(self):
        app = make_test_app()
        app.state.cart_svc.add_item  = AsyncMock(side_effect=ValueError("STOCK_UNAVAILABLE"))
        app.state.audit_svc.write    = AsyncMock()
        c = TestClient(app)
        resp = c.post(
            "/api/v1/cart/sess-1/add",
            headers=HEADERS,
            json={"product_id": "p1", "quantity": 100},
        )
        assert resp.status_code == 409

    def test_remove_item(self, client):
        resp = client.delete(
            "/api/v1/cart/sess-1/remove/p1",
            headers=HEADERS,
        )
        assert resp.status_code == 200


# ── Audit ─────────────────────────────────────────────────────────────────────

class TestAudit:
    @pytest.fixture
    def client(self):
        app = make_test_app()
        app.state.audit_svc.get_by_session = AsyncMock(return_value=[
            AuditLog(
                id=1, session_id="s1", event_type="CATALOG_SEARCH",
                actor="agent", reasoning="test", outcome="success",
                created_at=datetime.now(timezone.utc),
            )
        ])
        app.state.audit_svc.write         = AsyncMock()
        app.state.audit_svc.list_sessions = AsyncMock(return_value=[
            {"session_id": "s1", "goal": "buy shoes", "last_event": "ORDER_CONFIRMED",
             "event_count": 5, "started_at": "2026-01-01T00:00:00", "last_activity": "2026-01-01T01:00:00"}
        ])
        return TestClient(app)

    def test_get_by_session(self, client):
        resp = client.get("/audit/s1", headers=HEADERS)
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        assert data["logs"][0]["event_type"] == "CATALOG_SEARCH"

    def test_write_audit(self, client):
        resp = client.post(
            "/api/v1/audit",
            headers=HEADERS,
            json={"session_id": "s1", "event_type": "TEST", "actor": "agent", "outcome": "success"},
        )
        assert resp.status_code == 200
        assert resp.json() == {"status": "ok"}

    def test_write_audit_missing_fields(self, client):
        resp = client.post(
            "/api/v1/audit",
            headers=HEADERS,
            json={"session_id": "s1"},  # missing required fields
        )
        assert resp.status_code == 422

    def test_list_sessions(self, client):
        resp = client.get("/sessions", headers=HEADERS)
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["sessions"]) == 1


# ── Orders ────────────────────────────────────────────────────────────────────

class TestOrders:
    VALID_ITEMS = [
        {"product_id": "p1", "name": "X", "price_paise": 50000,
         "price_inr": 500.0, "quantity": 2, "reasoning": "", "image_url": ""}
    ]

    @pytest.fixture
    def client(self):
        app = make_test_app()
        app.state.pool.fetchrow    = AsyncMock(return_value={"id": "order-uuid-123"})
        app.state.audit_svc.write  = AsyncMock()
        app.state.payment_svc.verify_signature = MagicMock(return_value=True)
        return TestClient(app), app

    def test_create_order_success(self, client):
        c, app = client
        resp = c.post(
            "/api/v1/orders",
            headers=HEADERS,
            json={
                "session_id":        "s1",
                "razorpay_order_id": "rzp_order_abc",
                "amount_paise":      100000,
                "items":             self.VALID_ITEMS,
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "pending"
        assert "razorpay_order_id" in data

    def test_create_order_amount_mismatch(self, client):
        c, _ = client
        resp = c.post(
            "/api/v1/orders",
            headers=HEADERS,
            json={
                "session_id":        "s1",
                "razorpay_order_id": "rzp_order_abc",
                "amount_paise":      999,   # wrong — should be 100000
                "items":             self.VALID_ITEMS,
            },
        )
        assert resp.status_code == 400
        assert resp.json()["detail"]["error"] == "AMOUNT_MISMATCH"

    def test_create_order_empty_items(self, client):
        c, _ = client
        resp = c.post(
            "/api/v1/orders",
            headers=HEADERS,
            json={
                "session_id":        "s1",
                "razorpay_order_id": "rzp_order_abc",
                "amount_paise":      100000,
                "items":             [],   # empty → validation error
            },
        )
        assert resp.status_code == 422


# ── Analytics ─────────────────────────────────────────────────────────────────

class TestAnalytics:
    def test_analytics(self):
        app = make_test_app()
        # pool.fetchrow called 3 times for the 3 COUNT queries
        app.state.pool.fetchrow = AsyncMock(side_effect=[
            MagicMock(**{"__getitem__": lambda self, k: 5}),   # total_sessions
            MagicMock(**{"__getitem__": lambda self, k: 2}),   # total_orders
            MagicMock(**{"__getitem__": lambda self, k: 1}),   # guardrails
        ])
        from datetime import date
        app.state.pool.fetch = AsyncMock(return_value=[
            {"date": date(2026, 1, 1), "count": 10}
        ])
        c = TestClient(app)
        resp = c.get("/analytics", headers=HEADERS)
        assert resp.status_code == 200
        data = resp.json()
        assert "total_sessions"      in data
        assert "total_orders"        in data
        assert "guardrails_triggered" in data
        assert "timeline"            in data