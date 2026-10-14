"""
main.py — Python replacement for merchant-server/cmd/server/main.go

Starts FastAPI on the same port (8080), exposes identical routes,
uses the same middleware stack (CORS + API key auth + rate limit).
All other services (ai-agent, dashboard, postgres, redis, razorpay-mcp)
are untouched — only this binary changes.

Run:  uvicorn main:app --host 0.0.0.0 --port 8080
"""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

import db
from config import cfg
from middleware import AgentAuthMiddleware, CORSMiddleware, RateLimitMiddleware
from services.audit   import AuditService
from services.catalog import CatalogService
from services.cart    import CartService
from services.payment import PaymentService
from routers import audit, analytics, cart, catalog, order, resume, stream

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
log = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup / shutdown — mirrors Go's main() service wiring."""
    log.info("Merchant server starting on port :%s", cfg.port)

    await db.init_db(cfg.postgres_dsn, cfg.redis_url)

    # Wire services onto app.state so routers can access them via request.app.state
    app.state.pool        = db.pool
    app.state.redis       = db.redis
    app.state.audit_svc   = AuditService(db.pool, db.redis)
    app.state.catalog_svc = CatalogService(db.pool)
    app.state.cart_svc    = CartService(db.redis, app.state.catalog_svc)
    app.state.payment_svc = PaymentService(cfg.razorpay_secret)

    log.info("All services initialised")
    yield

    log.info("Shutting down...")
    await db.close_db()


app = FastAPI(
    title="PayAgent Merchant Server",
    description="Python replacement for the Go merchant-server. Identical API surface.",
    version="2.0.0",
    lifespan=lifespan,
    # Disable FastAPI's built-in docs in prod if needed; leave on for dev
    docs_url="/docs",
    redoc_url="/redoc",
)

# ── Middleware (order matters — applied inside-out in Starlette) ─────────────
# 1. CORS outermost so OPTIONS requests short-circuit immediately
app.add_middleware(CORSMiddleware)
# 2. Rate limiting
app.add_middleware(RateLimitMiddleware)
# 3. API key auth innermost (only runs after rate limit passes)
app.add_middleware(AgentAuthMiddleware, api_key=cfg.merchant_api_key)

# ── Health (unauthenticated — mirrors Go's r.GET("/health", ...)) ────────────
@app.get("/health", tags=["health"])
async def health():
    return {"status": "ok"}

# ── Routers ──────────────────────────────────────────────────────────────────
app.include_router(catalog.router)
app.include_router(cart.router)
app.include_router(audit.router)
app.include_router(order.router)
app.include_router(stream.router)
app.include_router(resume.router)
app.include_router(analytics.router)