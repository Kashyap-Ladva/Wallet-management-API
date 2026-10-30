import json
import logging
import os
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Optional
from uuid import UUID

from app.core.redis import get_redis_client

logger = logging.getLogger("app.cache")

# Cache configuration
CACHE_VERSION = os.getenv("CACHE_VERSION", "1")
ANALYTICS_DAILY_CACHE_TTL = int(os.getenv("ANALYTICS_DAILY_CACHE_TTL", "60"))
ANALYTICS_MONTHLY_CACHE_TTL = int(os.getenv("ANALYTICS_MONTHLY_CACHE_TTL", "300"))
ANALYTICS_DEFAULT_CACHE_TTL = int(os.getenv("ANALYTICS_DEFAULT_CACHE_TTL", "120"))


def _json_serial(obj: Any) -> Any:
    """JSON serializer for objects not serializable by default json code."""
    if isinstance(obj, Decimal):
        return str(obj)
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    if isinstance(obj, UUID):
        return str(obj)
    raise TypeError(f"Type {type(obj)} not serializable")


def build_cache_key(user_id: int, endpoint: str, **params: Any) -> str:
    """
    Generate deterministic cache key containing cache version, user ID, endpoint, and sorted params.
    Example: analytics:v1:u42:daily:date=2026-10-28
    """
    cleaned_params = {
        k: str(v)
        for k, v in params.items()
        if v is not None
    }
    if cleaned_params:
        params_str = ":".join(f"{k}={cleaned_params[k]}" for k in sorted(cleaned_params.keys()))
        return f"analytics:v{CACHE_VERSION}:u{user_id}:{endpoint}:{params_str}"
    return f"analytics:v{CACHE_VERSION}:u{user_id}:{endpoint}"


async def get_cached(key: str) -> Optional[Any]:
    """
    Retrieve cached data from Redis.
    Returns None on cache miss, connection failure, or deserialization error.
    """
    client = get_redis_client()
    if client is None:
        return None

    try:
        raw_val = await client.get(key)
        if raw_val is None:
            return None
        return json.loads(raw_val)
    except Exception as exc:
        logger.warning("Cache read failed for key %s: %s (falling back to database)", key, exc)
        return None


async def set_cached(key: str, data: Any, ttl: int) -> bool:
    """
    Serialize and store data in Redis with the given TTL in seconds.
    Returns True on success, False on failure.
    """
    client = get_redis_client()
    if client is None:
        return False

    try:
        serialized = json.dumps(data, default=_json_serial)
        await client.set(key, serialized, ex=ttl)
        return True
    except Exception as exc:
        logger.warning("Cache write failed for key %s: %s (non-fatal)", key, exc)
        return False


async def invalidate_user_analytics(user_id: int) -> int:
    """
    Safely invalidate all analytics cache entries for the given user.
    Uses SCAN to find keys with user namespace to avoid blocking Redis.
    Never raises an exception so calling database transactions are unaffected.
    """
    client = get_redis_client()
    if client is None:
        return 0

    match_pattern = f"analytics:*:u{user_id}:*"
    exact_pattern = f"analytics:*:u{user_id}"

    deleted_count = 0
    try:
        # Collect keys using scan_iter for both pattern styles
        keys_to_delete = []
        async for key in client.scan_iter(match=match_pattern):
            keys_to_delete.append(key)
        async for key in client.scan_iter(match=exact_pattern):
            if key not in keys_to_delete:
                keys_to_delete.append(key)

        if keys_to_delete:
            deleted_count = await client.delete(*keys_to_delete)
            logger.info("Invalidated %d cache keys for user %d", deleted_count, user_id)
        return deleted_count
    except Exception as exc:
        logger.warning(
            "Cache invalidation failed for user %d: %s. Relying on TTL expiration.",
            user_id,
            exc,
        )
        return 0
