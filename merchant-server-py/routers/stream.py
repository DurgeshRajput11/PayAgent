"""
routers/stream.py — mirrors internal/handlers/stream.go

GET /stream/{session_id}

SSE endpoint:
1. Replays historical audit logs from PostgreSQL (instant UI hydration on reload)
2. Subscribes to Redis pubsub channel for live events
Exactly mirrors Go's dual-source pattern.
"""
import asyncio
import json
import logging

import asyncpg
import redis.asyncio as aioredis
from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

from models import AuditLog

log    = logging.getLogger(__name__)
router = APIRouter(tags=["stream"])


@router.get("/stream/{session_id}")
async def stream(session_id: str, request: Request):
    pool:  asyncpg.Pool   = request.app.state.pool
    redis: aioredis.Redis = request.app.state.redis

    async def event_generator():
        # ── 1. Replay historical events from PostgreSQL ──────────────────
        try:
            rows = await pool.fetch(
                """
                SELECT id, session_id, event_type, actor, payload, reasoning, outcome, created_at
                FROM audit_logs
                WHERE session_id = $1
                ORDER BY id ASC
                """,
                session_id,
            )
            for row in rows:
                log_entry = AuditLog(
                    id=row["id"],
                    session_id=row["session_id"],
                    event_type=row["event_type"],
                    actor=row["actor"],
                    payload=row["payload"],
                    reasoning=row["reasoning"] or "",
                    outcome=row["outcome"] or "",
                    created_at=row["created_at"],
                )
                data = json.dumps(log_entry.model_dump(mode="json"), default=str)
                yield f"event: audit_log\ndata: {data}\n\n"
        except Exception as exc:
            log.error("Stream: error replaying history for %s: %s", session_id, exc)

        # ── 2. Subscribe to Redis for live events ────────────────────────
        pubsub = redis.pubsub()
        await pubsub.subscribe(f"audit:{session_id}")

        try:
            while True:
                # Check if the client disconnected
                if await request.is_disconnected():
                    break

                try:
                    msg = await asyncio.wait_for(
                        pubsub.get_message(ignore_subscribe_messages=True),
                        timeout=15.0,
                    )
                except asyncio.TimeoutError:
                    # Send a keep-alive comment to prevent proxy timeouts
                    yield ": keep-alive\n\n"
                    continue

                if msg and msg["type"] == "message":
                    yield f"event: audit_log\ndata: {msg['data']}\n\n"

        finally:
            await pubsub.unsubscribe(f"audit:{session_id}")
            await pubsub.aclose()

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control":               "no-cache",
            "Connection":                  "keep-alive",
            "X-Accel-Buffering":           "no",   # disable nginx buffering
            "Access-Control-Allow-Origin": "*",
        },
    )