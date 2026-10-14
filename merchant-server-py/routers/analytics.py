"""
routers/analytics.py — mirrors internal/handlers/analytics.go

GET /analytics

Returns total_sessions, total_orders, guardrails_triggered, and a
7-day event timeline — same queries as Go, same field names.
"""
import asyncpg
from fastapi import APIRouter, Request

router = APIRouter(tags=["analytics"])


@router.get("/analytics")
async def get_stats(request: Request):
    pool: asyncpg.Pool = request.app.state.pool

    stats: dict = {}

    # total_sessions
    row = await pool.fetchrow("SELECT COUNT(DISTINCT session_id) FROM audit_logs")
    stats["total_sessions"] = row[0] if row else 0

    # total_orders
    row = await pool.fetchrow(
        "SELECT COUNT(*) FROM audit_logs WHERE event_type = 'ORDER_CONFIRMED'"
    )
    stats["total_orders"] = row[0] if row else 0

    # guardrails_triggered
    row = await pool.fetchrow(
        "SELECT COUNT(*) FROM audit_logs WHERE event_type = 'GUARDRAIL_TRIGGERED'"
    )
    stats["guardrails_triggered"] = row[0] if row else 0

    # 7-day timeline — mirrors Go's DATE() + reverse order
    rows = await pool.fetch(
        """
        SELECT DATE(created_at) AS date, COUNT(*) AS count
        FROM audit_logs
        GROUP BY date
        ORDER BY date DESC
        LIMIT 7
        """
    )
    timeline = [
        {"date": str(r["date"]), "events": r["count"]}
        for r in reversed(rows)   # reverse to chronological order, as Go does
    ]
    stats["timeline"] = timeline

    return stats