"""
db.py — mirrors internal/db/postgres.go and internal/db/redis.go
Provides a module-level asyncpg pool and redis.asyncio client.
Call init_db() once at startup (lifespan).
"""
import asyncpg
import redis.asyncio as aioredis
import logging

log = logging.getLogger(__name__)

# Module-level singletons — set by init_db() at startup
pool:  asyncpg.Pool        = None   # type: ignore[assignment]
redis: aioredis.Redis      = None   # type: ignore[assignment]


async def init_db(postgres_dsn: str, redis_url: str) -> None:
    global pool, redis

    pool = await asyncpg.create_pool(
        postgres_dsn,
        min_size=2,
        max_size=10,
        # asyncpg returns JSON as str by default; decode it so JSONB
        # columns come back as dicts/lists, matching Go's json.RawMessage.
        init=_set_json_codec,
    )
    log.info("Connected to PostgreSQL")

    redis = aioredis.from_url(redis_url, decode_responses=True)
    await redis.ping()
    log.info("Connected to Redis")


async def close_db() -> None:
    if pool:
        await pool.close()
    if redis:
        await redis.aclose()


async def _set_json_codec(conn: asyncpg.Connection) -> None:
    """
    Register json/jsonb codecs so asyncpg encodes/decodes them automatically,
    exactly as pgx does in Go.
    """
    import json
    await conn.set_type_codec(
        "json",
        encoder=json.dumps,
        decoder=json.loads,
        schema="pg_catalog",
    )
    await conn.set_type_codec(
        "jsonb",
        encoder=json.dumps,
        decoder=json.loads,
        schema="pg_catalog",
    )