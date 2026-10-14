"""
middleware.py — mirrors internal/middleware/auth.go and internal/middleware/ratelimit.go

AgentAuth: validates X-API-Key header with constant-time compare.
RateLimit:  60 requests/minute per IP using slowapi (token-bucket).
"""
import hmac
from collections import defaultdict
from datetime import datetime, timedelta, timezone

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware


# ── API Key Auth ─────────────────────────────────────────────────────────────

class AgentAuthMiddleware(BaseHTTPMiddleware):
    """
    Validates the X-API-Key header on every request except /health.
    Uses hmac.compare_digest (constant-time) to prevent timing attacks,
    mirroring Go's subtle.ConstantTimeCompare.
    """
    def __init__(self, app, api_key: str) -> None:
        super().__init__(app)
        self._api_key = api_key

    async def dispatch(self, request: Request, call_next):
        # /health is always open — mirrors Go's unauthenticated /health route
        if request.url.path == "/health":
            return await call_next(request)

        # OPTIONS pre-flight — return 204 directly (CORS middleware sets headers)
        if request.method == "OPTIONS":
            return JSONResponse(status_code=204, content=None)

        key = request.headers.get("X-API-Key", "")
        # constant-time compare — both must be non-empty, then compare
        if not key or not hmac.compare_digest(key.encode(), self._api_key.encode()):
            return JSONResponse(status_code=401, content={"error": "UNAUTHORIZED"})

        return await call_next(request)


# ── CORS ─────────────────────────────────────────────────────────────────────
# Mirrors Go's permissive CORS (this server is only reached via Next.js proxy)

CORS_HEADERS = {
    "Access-Control-Allow-Origin":  "*",
    "Access-Control-Allow-Headers": "Content-Type, X-API-Key",
    "Access-Control-Allow-Methods": "GET, POST, DELETE, OPTIONS",
}


class CORSMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if request.method == "OPTIONS":
            return JSONResponse(status_code=204, headers=CORS_HEADERS)

        response = await call_next(request)
        for k, v in CORS_HEADERS.items():
            response.headers[k] = v
        return response


# ── Rate Limiting ─────────────────────────────────────────────────────────────
# Simple in-process counter per IP, mirroring Go's visitor map.
# 60 requests per 60-second sliding window.

_visitors: dict[str, list[datetime]] = defaultdict(list)
_MAX_PER_MINUTE = 60


class RateLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if request.url.path == "/health":
            return await call_next(request)

        ip  = request.client.host if request.client else "unknown"
        now = datetime.now(timezone.utc)
        window_start = now - timedelta(minutes=1)

        # Prune old entries
        _visitors[ip] = [t for t in _visitors[ip] if t > window_start]
        _visitors[ip].append(now)

        if len(_visitors[ip]) > _MAX_PER_MINUTE:
            return JSONResponse(
                status_code=429,
                content={"error": "Rate limit exceeded"},
            )

        return await call_next(request)