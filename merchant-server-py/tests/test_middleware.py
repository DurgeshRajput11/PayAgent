"""
tests/test_middleware.py
Tests API key auth, CORS, and rate limiting middleware.
Uses FastAPI TestClient (sync) — no real DB needed.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi import FastAPI
from fastapi.testclient import TestClient

from middleware import AgentAuthMiddleware, CORSMiddleware, RateLimitMiddleware


def make_app(api_key: str = "test-key") -> FastAPI:
    app = FastAPI()
    app.add_middleware(CORSMiddleware)
    app.add_middleware(RateLimitMiddleware)
    app.add_middleware(AgentAuthMiddleware, api_key=api_key)

    @app.get("/health")
    def health():
        return {"status": "ok"}

    @app.get("/protected")
    def protected():
        return {"data": "secret"}

    return app


class TestAgentAuth:
    def test_health_no_key_returns_200(self):
        client = TestClient(make_app())
        resp = client.get("/health")
        assert resp.status_code == 200

    def test_protected_no_key_returns_401(self):
        client = TestClient(make_app())
        resp = client.get("/protected")
        assert resp.status_code == 401
        assert resp.json()["error"] == "UNAUTHORIZED"

    def test_protected_wrong_key_returns_401(self):
        client = TestClient(make_app())
        resp = client.get("/protected", headers={"X-API-Key": "wrong"})
        assert resp.status_code == 401

    def test_protected_correct_key_returns_200(self):
        client = TestClient(make_app())
        resp = client.get("/protected", headers={"X-API-Key": "test-key"})
        assert resp.status_code == 200
        assert resp.json() == {"data": "secret"}

    def test_options_passes_through(self):
        client = TestClient(make_app(), raise_server_exceptions=False)
        resp = client.options("/protected")
        # OPTIONS should not be blocked by auth
        assert resp.status_code in (200, 204)


class TestCORSHeaders:
    def test_cors_headers_present(self):
        client = TestClient(make_app())
        resp = client.get("/health")
        assert resp.headers.get("access-control-allow-origin") == "*"
        assert "Content-Type" in resp.headers.get("access-control-allow-headers", "")


class TestPaymentService:
    """Payment signature verification — mirrors Go's PaymentService tests."""

    def test_valid_signature(self):
        from services.payment import PaymentService
        import hashlib, hmac as _hmac
        secret   = "test_secret"
        order_id = "order_abc123"
        pay_id   = "pay_xyz789"
        sig      = _hmac.new(secret.encode(), f"{order_id}|{pay_id}".encode(), hashlib.sha256).hexdigest()

        svc = PaymentService(secret)
        assert svc.verify_signature(order_id, pay_id, sig) is True

    def test_invalid_signature(self):
        from services.payment import PaymentService
        svc = PaymentService("test_secret")
        assert svc.verify_signature("order_abc", "pay_xyz", "badsig") is False

    def test_empty_secret_returns_false(self):
        from services.payment import PaymentService
        svc = PaymentService("")
        assert svc.verify_signature("order_abc", "pay_xyz", "anysig") is False

    def test_empty_fields_return_false(self):
        from services.payment import PaymentService
        svc = PaymentService("secret")
        assert svc.verify_signature("", "pay_xyz", "sig") is False
        assert svc.verify_signature("order_abc", "", "sig") is False
        assert svc.verify_signature("order_abc", "pay_xyz", "") is False