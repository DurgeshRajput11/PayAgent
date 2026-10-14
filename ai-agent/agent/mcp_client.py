"""
Thin helper for calling the Razorpay MCP server from the LangGraph agent.

A short-lived MCP session is opened per call rather than kept as a global
persistent connection. For the call volume here (one or two payment-order
creations per shopping session) the extra round trip to open a session is a
few milliseconds and not worth the complexity of managing a long-lived
client's lifecycle inside a FastAPI app that may reload workers.
"""

import os
import json
import logging
from typing import Any

from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

logger = logging.getLogger("payagent.mcp_client")

RAZORPAY_MCP_URL = os.getenv("RAZORPAY_MCP_URL", "http://localhost:3010/mcp")
RAZORPAY_MCP_AUTH_TOKEN = os.getenv("RAZORPAY_MCP_AUTH_TOKEN", "")


class MCPToolError(Exception):
    """Raised when the MCP tool call itself reports an error (e.g. Razorpay
    rejected the request), as opposed to a transport/connection failure."""


async def call_razorpay_tool(tool_name: str, arguments: dict[str, Any]) -> dict:
    """Open an MCP session against the Razorpay MCP server, call one tool,
    and return its result as a plain dict."""
    headers = {}
    if RAZORPAY_MCP_AUTH_TOKEN:
        headers["Authorization"] = f"Bearer {RAZORPAY_MCP_AUTH_TOKEN}"

    async with streamablehttp_client(RAZORPAY_MCP_URL, headers=headers) as (read, write, _):
        async with ClientSession(read, write) as session:
            await session.initialize()
            result = await session.call_tool(tool_name, arguments)

    if result.isError:
        message = "".join(
            block.text for block in result.content if getattr(block, "type", None) == "text"
        ) or f"{tool_name} failed"
        raise MCPToolError(message)

    if result.structuredContent is not None:
        return result.structuredContent

    # Fall back to parsing the first text block as JSON if the server
    # didn't return structured content for some reason.
    for block in result.content:
        if getattr(block, "type", None) == "text":
            try:
                return json.loads(block.text)
            except json.JSONDecodeError:
                return {"raw": block.text}

    return {}
