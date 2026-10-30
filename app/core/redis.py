import logging
import os
from typing import Optional

import redis.asyncio as aioredis
from fastapi import FastAPI

logger = logging.getLogger("app.redis")

# Global client reference
_redis_client: Optional[aioredis.Redis] = None


def get_redis_url() -> str:
    return os.getenv("REDIS_URL", "redis://localhost:6379/0")


def get_redis_connect_timeout() -> float:
    try:
        return float(os.getenv("REDIS_CONNECT_TIMEOUT", "2.0"))
    except (ValueError, TypeError):
        return 2.0


def get_redis_socket_timeout() -> float:
    try:
        return float(os.getenv("REDIS_SOCKET_TIMEOUT", "2.0"))
    except (ValueError, TypeError):
        return 2.0


async def init_redis(app: Optional[FastAPI] = None) -> Optional[aioredis.Redis]:
    """
    Initialize a reusable asynchronous Redis client with connection timeouts.
    Stores the client in app.state.redis and module global.
    """
    global _redis_client
    redis_url = get_redis_url()
    connect_timeout = get_redis_connect_timeout()
    socket_timeout = get_redis_socket_timeout()

    try:
        client = aioredis.from_url(
            redis_url,
            encoding="utf-8",
            decode_responses=True,
            socket_connect_timeout=connect_timeout,
            socket_timeout=socket_timeout,
            health_check_interval=30,
        )
        # Attempt connection check
        try:
            await client.ping()
            logger.info("Connected to Redis successfully at %s", redis_url)
        except Exception as exc:
            logger.warning(
                "Redis client initialized but ping failed at %s: %s (will retry on demand)",
                redis_url,
                exc,
            )

        _redis_client = client
        if app is not None:
            app.state.redis = client
        return client
    except Exception as exc:
        logger.error("Failed to initialize Redis client for %s: %s", redis_url, exc)
        _redis_client = None
        if app is not None:
            app.state.redis = None
        return None


async def close_redis(app: Optional[FastAPI] = None) -> None:
    """Cleanly shutdown the Redis client."""
    global _redis_client
    client = getattr(app.state, "redis", None) if app is not None else _redis_client
    if client is not None:
        try:
            if hasattr(client, "aclose"):
                await client.aclose()
            else:
                await client.close()
            logger.info("Redis client closed cleanly")
        except Exception as exc:
            logger.error("Error closing Redis client: %s", exc)
    _redis_client = None
    if app is not None:
        app.state.redis = None


def get_redis_client() -> Optional[aioredis.Redis]:
    """Return the global Redis client instance."""
    return _redis_client


def set_redis_client(client: Optional[aioredis.Redis]) -> None:
    """Set the Redis client instance (useful for testing and mocks)."""
    global _redis_client
    _redis_client = client


async def check_redis_health() -> str:
    """
    Returns 'connected' if Redis responds to ping, otherwise 'unavailable'.
    """
    client = get_redis_client()
    if client is None:
        return "unavailable"
    try:
        pong = await client.ping()
        return "connected" if pong else "unavailable"
    except Exception as exc:
        logger.warning("Redis health ping failed: %s", exc)
        return "unavailable"
