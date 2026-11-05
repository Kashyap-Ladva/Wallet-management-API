from datetime import date
import json
import logging
import os
import redis

from sqlalchemy.exc import DBAPIError, OperationalError

from app.core.celery_app import celery_app
from app.database import get_task_db
from app.services import analytics_service
from app.services.cache_service import (
    ANALYTICS_DAILY_CACHE_TTL,
    ANALYTICS_MONTHLY_CACHE_TTL,
    _json_serial,
    build_cache_key,
)

logger = logging.getLogger("app.jobs.analytics")


@celery_app.task(
    name="app.jobs.analytics.warm_user_analytics_cache_task",
    bind=True,
    max_retries=3,
    default_retry_delay=30,
    autoretry_for=(OperationalError, DBAPIError),
    retry_backoff=True,
)
def warm_user_analytics_cache_task(self, user_id: int) -> dict:
    """
    Background cache warming task. Pre-computes and caches daily and monthly
    analytics in Redis without blocking FastAPI request threads.
    """
    today = date.today()
    redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")

    with get_task_db() as db:
        daily_data = analytics_service.get_daily_summary(db, user_id, today)
        monthly_data = analytics_service.get_monthly_summary(db, user_id, today.year, today.month)

    try:
        client = redis.Redis.from_url(redis_url, decode_responses=True, socket_timeout=2.0)
        daily_key = build_cache_key(user_id, "daily", date=today.isoformat())
        monthly_key = build_cache_key(user_id, "monthly", year=today.year, month=today.month)

        client.set(daily_key, json.dumps(daily_data, default=_json_serial), ex=ANALYTICS_DAILY_CACHE_TTL)
        client.set(monthly_key, json.dumps(monthly_data, default=_json_serial), ex=ANALYTICS_MONTHLY_CACHE_TTL)
        logger.info("Successfully pre-warmed analytics cache for user %d", user_id)
        return {
            "status": "SUCCESS",
            "user_id": user_id,
            "daily_cached": True,
            "monthly_cached": True,
        }
    except Exception as exc:
        logger.warning("Failed to warm analytics cache in Redis for user %d: %s", user_id, exc)
        return {"status": "FAILED", "reason": str(exc), "user_id": user_id}

