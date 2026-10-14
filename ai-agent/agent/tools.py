import os
import time
from typing import Optional

import httpx
from langchain_core.tools import tool

from agent.mcp_client import call_razorpay_tool, MCPToolError

MERCHANT_BASE_URL = os.getenv("MERCHANT_BASE_URL", "http://localhost:8080")
MERCHANT_API_KEY = os.getenv("MERCHANT_API_KEY", "internal-agent-api-key-change-in-prod")

HEADERS = {"X-API-Key": MERCHANT_API_KEY, "Content-Type": "application/json"}


class ToolHTTPError(Exception):
    """Raised when an HTTP call to the merchant server exhausts its retries
    or fails outright. Tools catch this and return a structured error dict
    instead of letting it propagate, so the agent can react to a failure
    (e.g. suggest an alternative) instead of crashing the graph."""


def _request_with_retry(method: str, url: str, max_retries: int = 2, **kwargs) -> httpx.Response:
    """Execute an HTTP request with exponential backoff retry.
    Raises ToolHTTPError on exhaustion instead of silently returning None,
    which the previous version could do for an unrecognized method.
    """
    kwargs.setdefault("timeout", 10)
    methods = {
        "GET": httpx.get,
        "POST": httpx.post,
        "DELETE": httpx.delete,
        "PATCH": httpx.patch,
    }
    if method not in methods:
        raise ValueError(f"Unsupported HTTP method: {method}")

    last_error: Optional[Exception] = None
    for attempt in range(max_retries + 1):
        try:
            resp = methods[method](url, **kwargs)
            resp.raise_for_status()
            return resp
        except (httpx.ConnectError, httpx.TimeoutException, httpx.HTTPStatusError) as e:
            last_error = e
            if attempt == max_retries:
                break
            time.sleep(0.5 * (2**attempt))

    raise ToolHTTPError(str(last_error))


def _safe_call(method: str, url: str, **kwargs) -> dict:
    """Wraps _request_with_retry for tools that just want a dict back,
    converting network failures into a structured error the LLM can read
    instead of a raw exception."""
    try:
        resp = _request_with_retry(method, url, **kwargs)
        return resp.json()
    except ToolHTTPError as e:
        return {"error": str(e), "status": "TOOL_ERROR"}


@tool
def catalog_search(session_id: str, query: str = "", category: str = "", max_price_inr: float = 0, min_price_inr: float = 0) -> dict:
    """Search the product catalog by keyword, category, or price range.
    Always call this before suggesting, comparing, or adding products to cart.
    Returns a list of matching products with their IDs, names, prices, descriptions, stock, and tags.
    """
    params = {}
    if query:
        params["q"] = query
    if category:
        params["category"] = category
    if max_price_inr > 0:
        params["max_price_inr"] = max_price_inr
    if min_price_inr > 0:
        params["min_price_inr"] = min_price_inr

    headers = {**HEADERS, "X-Session-ID": session_id}
    return _safe_call("GET", f"{MERCHANT_BASE_URL}/api/v1/catalog/search", params=params, headers=headers)


@tool
def catalog_get_product(product_id: str) -> dict:
    """Fetch full details of a single product by its ID.
    Use this when the user asks 'tell me more about X', 'what are the full specs of Y?',
    or when you need to verify stock or description before recommending.
    """
    return _safe_call("GET", f"{MERCHANT_BASE_URL}/api/v1/catalog/{product_id}", headers=HEADERS)


@tool
def catalog_compare(session_id: str, product_ids: list) -> dict:
    """Compare multiple products side-by-side given a list of product IDs.
    Use this when the user says 'compare these', 'which is better?', 'difference between X and Y'.
    Returns a structured comparison of all products with price, stock, features, and value rating.
    """
    products = []
    for pid in product_ids:
        product = _safe_call("GET", f"{MERCHANT_BASE_URL}/api/v1/catalog/{pid}", headers=HEADERS)
        if "error" in product:
            products.append({"id": pid, "error": product["error"]})
        else:
            products.append(product)

    if not products:
        return {"error": "No products found to compare"}

    comparison = {
        "products": products,
        "summary": {
            "cheapest": min(products, key=lambda p: p.get("price_paise", float("inf"))).get("name", "N/A"),
            "most_expensive": max(products, key=lambda p: p.get("price_paise", 0)).get("name", "N/A"),
            "best_stocked": max(products, key=lambda p: p.get("stock", 0)).get("name", "N/A"),
        },
    }
    return comparison


@tool
def cart_add(session_id: str, product_id: str, quantity: int, agent_reasoning: str) -> dict:
    """Add a product to the session cart.
    Always provide reasoning explaining why this specific product was chosen.
    Use catalog_search or catalog_get_product first to confirm the product exists.
    """
    payload = {
        "product_id": product_id,
        "quantity": quantity,
        "agent_reasoning": agent_reasoning,
    }
    return _safe_call("POST", f"{MERCHANT_BASE_URL}/api/v1/cart/{session_id}/add", json=payload, headers=HEADERS)


@tool
def cart_get(session_id: str) -> dict:
    """Retrieve the current cart contents, item details, and total price for a session.
    Use this to show the user what's in their cart or before proceeding to checkout.
    """
    return _safe_call("GET", f"{MERCHANT_BASE_URL}/api/v1/cart/{session_id}", headers=HEADERS)


@tool
def cart_remove(session_id: str, product_id: str, quantity: int = 0) -> dict:
    """Remove a specific product from the cart or decrease its quantity.
    If quantity > 0, it decreases the quantity by that amount.
    If quantity is 0 or not provided, it removes the item entirely.
    """
    url = f"{MERCHANT_BASE_URL}/api/v1/cart/{session_id}/remove/{product_id}"
    if quantity > 0:
        url += f"?qty={quantity}"
    return _safe_call("DELETE", url, headers=HEADERS)


@tool
def cart_clear(session_id: str) -> dict:
    """Remove ALL items from the cart at once.
    Use when user says 'clear my cart', 'start over', 'empty the cart'.
    """
    cart = _safe_call("GET", f"{MERCHANT_BASE_URL}/api/v1/cart/{session_id}", headers=HEADERS)
    if "error" in cart:
        return cart

    items = cart.get("items", [])
    removed = []
    for item in items:
        pid = item.get("product_id")
        if pid:
            _safe_call("DELETE", f"{MERCHANT_BASE_URL}/api/v1/cart/{session_id}/remove/{pid}", headers=HEADERS)
            removed.append(pid)
    return {"cleared": True, "items_removed": len(removed)}


@tool
async def razorpay_create_order(session_id: str, amount_paise: int, currency: str = "INR") -> dict:
    """Create a Razorpay payment order for the user's cart. ONLY call this after
    the user explicitly says they want to checkout/buy/pay. This will pause the
    agent and require human approval before executing.
    amount_paise is the total in paise (INR x 100). E.g., Rs.1499 = 149900 paise.

    The amount is cross-checked against the live cart total on the merchant
    server, so this cannot be used to create an order for more than what's
    actually in the cart.
    """
    cart = _safe_call("GET", f"{MERCHANT_BASE_URL}/api/v1/cart/{session_id}", headers=HEADERS)
    if "error" in cart:
        return cart

    cart_total_paise = cart.get("total_paise", 0)
    items = cart.get("items", [])

    if not items:
        return {"error": "CART_EMPTY", "status": "TOOL_ERROR"}
    if amount_paise != cart_total_paise:
        return {
            "error": "AMOUNT_MISMATCH",
            "message": f"Requested amount ({amount_paise} paise) does not match the live cart total ({cart_total_paise} paise). Use the cart total.",
            "status": "TOOL_ERROR",
        }

    try:
        rzp_order = await call_razorpay_tool(
            "create_order",
            {"amount_paise": amount_paise, "currency": currency, "receipt": session_id},
        )
    except MCPToolError as e:
        return {"error": f"RAZORPAY_ERROR: {e}", "status": "TOOL_ERROR"}

    if "id" not in rzp_order:
        return {"error": "Razorpay did not return an order id", "status": "TOOL_ERROR", "raw": rzp_order}

    # Persist the order with the REAL cart items (previously this sent an
    # empty {} for items, so the merchant server could never validate the
    # charge against what was actually being bought, and stock could never
    # be decremented on payment confirmation).
    go_payload = {
        "session_id": session_id,
        "razorpay_order_id": rzp_order["id"],
        "amount_paise": amount_paise,
        "items": items,
    }
    merchant_order = _safe_call("POST", f"{MERCHANT_BASE_URL}/api/v1/orders", json=go_payload, headers=HEADERS)
    rzp_order["merchant_order"] = merchant_order

    return rzp_order


TOOLS = [
    catalog_search,
    catalog_get_product,
    catalog_compare,
    cart_add,
    cart_get,
    cart_remove,
    cart_clear,
    razorpay_create_order,
]
