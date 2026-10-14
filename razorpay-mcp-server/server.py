"""
A small Model Context Protocol server for Razorpay, in Python.

This replaces the previous setup, where docker-compose pulled the official
`razorpay/mcp:latest` Node.js image, the README and dashboard both advertised
"Powered by Razorpay MCP", but the Python agent actually called
api.razorpay.com directly with httpx and never spoke MCP to anything. That
container existed but was wired to nothing.

This server exposes exactly the Razorpay operations PayAgent needs
(create_order, fetch_order, fetch_payment, capture_payment) over the
streamable-http MCP transport, authenticating to Razorpay itself with the
account's key id/secret. It holds RAZORPAY_KEY_SECRET — nothing else in the
stack needs to.

Payment signature verification is intentionally NOT exposed here: the Go
merchant server verifies Razorpay checkout signatures itself (see
merchant-server/internal/services/payment.go) right before it mints the
"order paid" state and decrements stock, inside one database transaction.
Routing that specific check through an HTTP+MCP round trip would only add a
network hop to the one step where correctness matters most, for no benefit.
"""

import os
import logging
from typing import Any

import httpx
from mcp.server.fastmcp import FastMCP
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("razorpay-mcp")

RAZORPAY_API_BASE = "https://api.razorpay.com/v1"
RAZORPAY_KEY_ID = os.getenv("RAZORPAY_KEY_ID", "")
RAZORPAY_KEY_SECRET = os.getenv("RAZORPAY_KEY_SECRET", "")

# A simple shared-secret check for the MCP endpoint itself, so this server
# isn't an open proxy onto your Razorpay account for anyone who can reach
# its port on the Docker network.
MCP_AUTH_TOKEN = os.getenv("RAZORPAY_MCP_AUTH_TOKEN", "")

mcp = FastMCP(
    name="razorpay-mcp",
    host="0.0.0.0",
    port=int(os.getenv("PORT", "3000")),
    stateless_http=True,
)


def _auth() -> tuple[str, str] | None:
    if not RAZORPAY_KEY_ID or not RAZORPAY_KEY_SECRET:
        return None
    return (RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET)


async def _razorpay_request(method: str, path: str, **kwargs: Any) -> dict:
    auth = _auth()
    if auth is None:
        raise RuntimeError(
            "RAZORPAY_KEY_ID / RAZORPAY_KEY_SECRET are not configured on the MCP server"
        )

    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.request(
            method, f"{RAZORPAY_API_BASE}{path}", auth=auth, **kwargs
        )
        if resp.status_code >= 400:
            # Razorpay returns {"error": {"description": ..., "code": ...}}
            try:
                detail = resp.json().get("error", {}).get("description", resp.text)
            except Exception:
                detail = resp.text
            raise RuntimeError(f"Razorpay API error ({resp.status_code}): {detail}")
        return resp.json()


@mcp.tool()
async def create_order(
    amount_paise: int,
    currency: str = "INR",
    receipt: str = "",
    notes: dict[str, str] | None = None,
) -> dict:
    """Create a Razorpay order for a checkout session.

    amount_paise is the total amount in paise (INR x 100). Returns the
    Razorpay order object, including its `id`, which the client later passes
    to Razorpay Checkout to actually collect payment.
    """
    if amount_paise <= 0:
        raise ValueError("amount_paise must be a positive integer")

    payload: dict[str, Any] = {"amount": amount_paise, "currency": currency}
    if receipt:
        payload["receipt"] = receipt
    if notes:
        payload["notes"] = notes

    order = await _razorpay_request("POST", "/orders", json=payload)
    logger.info("Created Razorpay order %s for %d paise", order.get("id"), amount_paise)
    return order


@mcp.tool()
async def fetch_order(razorpay_order_id: str) -> dict:
    """Fetch a Razorpay order by its ID, including its current status
    (created / attempted / paid)."""
    return await _razorpay_request("GET", f"/orders/{razorpay_order_id}")


@mcp.tool()
async def fetch_payment(razorpay_payment_id: str) -> dict:
    """Fetch a Razorpay payment by its ID, including its status
    (created / authorized / captured / refunded / failed)."""
    return await _razorpay_request("GET", f"/payments/{razorpay_payment_id}")


@mcp.tool()
async def capture_payment(
    razorpay_payment_id: str, amount_paise: int, currency: str = "INR"
) -> dict:
    """Capture an authorized payment. Most Checkout.js integrations (this
    one included) auto-capture on success, so this is mainly useful for
    manual-capture flows or retrying a payment stuck in `authorized`."""
    payload = {"amount": amount_paise, "currency": currency}
    return await _razorpay_request(
        "POST", f"/payments/{razorpay_payment_id}/capture", json=payload
    )


@mcp.custom_route("/health", methods=["GET"])
async def health(_request: Request) -> JSONResponse:
    configured = bool(RAZORPAY_KEY_ID and RAZORPAY_KEY_SECRET)
    return JSONResponse({"status": "ok", "razorpay_configured": configured})


class _TokenAuthMiddleware:
    """Requires 'Authorization: Bearer <RAZORPAY_MCP_AUTH_TOKEN>' on every
    request except /health. A no-op if RAZORPAY_MCP_AUTH_TOKEN isn't set,
    which is fine for local docker-compose dev where this port isn't
    published to the host.

    Written as a plain ASGI middleware (not Starlette's BaseHTTPMiddleware,
    which buffers the whole response) because the streamable-http transport
    uses long-lived streaming responses that a buffering middleware would
    break.
    """

    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or not MCP_AUTH_TOKEN or scope["path"] == "/health":
            await self.app(scope, receive, send)
            return

        request = Request(scope, receive)
        expected = f"Bearer {MCP_AUTH_TOKEN}"
        if request.headers.get("authorization") != expected:
            response = JSONResponse({"error": "UNAUTHORIZED"}, status_code=401)
            await response(scope, receive, send)
            return

        await self.app(scope, receive, send)


def build_app() -> ASGIApp:
    app: Starlette = mcp.streamable_http_app()
    return _TokenAuthMiddleware(app)


if __name__ == "__main__":
    if not MCP_AUTH_TOKEN:
        logger.warning(
            "RAZORPAY_MCP_AUTH_TOKEN is not set — this MCP server is reachable "
            "by anything on its network with no credential. Fine for local dev, "
            "set it for anything beyond that."
        )
    import uvicorn

    uvicorn.run(build_app(), host="0.0.0.0", port=int(os.getenv("PORT", "3000")))
