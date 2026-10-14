"""
services/audit.py — mirrors internal/services/audit.go
Dual-writes to PostgreSQL (persistent) and publishes to Redis (SSE).
"""
import json
import logging
from datetime import datetime, timezone

import asyncpg
import redis.asyncio as aioredis

from models import AuditLog

log = logging.getLogger(__name__)


class AuditService:
    def __init__(self, pool: asyncpg.Pool, rdb: aioredis.Redis) -> None:
        self.pool  = pool
        self.redis = rdb

    async def write(self, entry: AuditLog) -> None:
        entry.created_at = datetime.now(timezone.utc)

        payload_json = json.dumps(entry.payload) if entry.payload is not None else None

        try:
            row = await self.pool.fetchrow(
                """
                INSERT INTO audit_logs
                    (session_id, event_type, actor, payload, reasoning, outcome, created_at)
                VALUES ($1, $2, $3, $4::jsonb, $5, $6, $7)
                RETURNING id
                """,
                entry.session_id,
                entry.event_type,
                entry.actor,
                payload_json,
                entry.reasoning,
                entry.outcome,
                entry.created_at,
            )
            entry.id = row["id"]
        except Exception as exc:
            log.error("Failed to write audit log: %s", exc)
            return

        # Publish to Redis channel for SSE streaming — mirrors Go's Publish call
        data = entry.model_dump(mode="json")
        await self.redis.publish(f"audit:{entry.session_id}", json.dumps(data, default=str))

    async def get_by_session(self, session_id: str) -> list[AuditLog]:
        rows = await self.pool.fetch(
            """
            SELECT id, session_id, event_type, actor, payload, reasoning, outcome, created_at
            FROM audit_logs
            WHERE session_id = $1
            ORDER BY id ASC
            """,
            session_id,
        )
        return [
            AuditLog(
                id=r["id"],
                session_id=r["session_id"],
                event_type=r["event_type"],
                actor=r["actor"],
                payload=r["payload"],
                reasoning=r["reasoning"] or "",
                outcome=r["outcome"] or "",
                created_at=r["created_at"],
            )
            for r in rows
        ]

    async def list_sessions(self) -> list[dict]:
        """
        Mirrors AuditHandler.ListSessions SQL query exactly — same columns,
        same ordering, same LIMIT 50.
        """
        rows = await self.pool.fetch(
            """
            SELECT session_id,
                   COALESCE(
                       MIN(reasoning) FILTER (WHERE event_type = 'USER_GOAL'),
                       MIN(reasoning) FILTER (WHERE event_type = 'CATALOG_SEARCH')
                   ) AS goal,
                   MAX(event_type) AS last_event,
                   COUNT(*)        AS event_count,
                   MIN(created_at) AS started_at,
                   MAX(created_at) AS last_activity
            FROM audit_logs
            GROUP BY session_id
            ORDER BY MAX(created_at) DESC
            LIMIT 50
            """
        )
        return [
            {
                "session_id":    r["session_id"],
                "goal":          r["goal"],
                "last_event":    r["last_event"],
                "event_count":   r["event_count"],
                "started_at":    r["started_at"].isoformat() if r["started_at"] else None,
                "last_activity": r["last_activity"].isoformat() if r["last_activity"] else None,
            }
            for r in rows
        ]