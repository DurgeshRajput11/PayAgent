"""
config.py — mirrors merchant-server/internal/config/config.go
Reads .env from project root (../../.env relative to this file) exactly
the same way the Go version does.
"""
import os
from pathlib import Path
from dotenv import load_dotenv

# Walk up until we find .env, mirroring Go's "../.env", ".env", "../../.env" search
for candidate in [
    Path(__file__).parent / ".env",
    Path(__file__).parent.parent / ".env",
    Path(__file__).parent.parent.parent / ".env",
]:
    if candidate.exists():
        load_dotenv(candidate)
        break


def _get(key: str, default: str = "") -> str:
    return os.environ.get(key, default)


def _build_dsn() -> str:
    host     = _get("POSTGRES_HOST", "postgres")
    port     = _get("POSTGRES_PORT", "5432")
    user     = _get("POSTGRES_USER", "payagent")
    password = _get("POSTGRES_PASSWORD", "payagent_secret")
    db       = _get("POSTGRES_DB", "payagent")
    return f"postgresql://{user}:{password}@{host}:{port}/{db}"


class Config:
    port:                    str = _get("MERCHANT_SERVER_PORT", "8080")
    postgres_dsn:            str = _build_dsn()
    redis_url:               str = _get("REDIS_URL", "redis://redis:6379")
    merchant_api_key:        str = _get("MERCHANT_API_KEY", "dev-key")
    razorpay_key_id:         str = _get("RAZORPAY_KEY_ID", "")
    razorpay_secret:         str = _get("RAZORPAY_KEY_SECRET", "")
    razorpay_webhook_secret: str = _get("RAZORPAY_WEBHOOK_SECRET", "")
    agent_service_url:       str = _get("AGENT_SERVICE_URL", "http://ai-agent:8001")
    agent_service_key:       str = _get("AGENT_SERVICE_API_KEY", "dev-agent-key")


cfg = Config()