import logging
import os
import time
from urllib.parse import urlparse, urlunparse

from celery import Celery
from celery.schedules import crontab
from celery.signals import task_failure, task_postrun, task_prerun, task_retry
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger("app.celery")


def _get_isolated_redis_url(default_db: int) -> str:
    """
    Derive an isolated Redis DB URL from REDIS_URL if an explicit URL is not configured.
    Ensures broker (DB 1) and result backend (DB 2) never collide with caching/rate limiting (DB 0).
    """
    raw_redis = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    try:
        parsed = urlparse(raw_redis)
        path = f"/{default_db}"
        return urlunparse((parsed.scheme, parsed.netloc, path, parsed.params, parsed.query, parsed.fragment))
    except Exception:
        return f"redis://localhost:6379/{default_db}"


# Broker & Result Backend URLs with logical Redis DB isolation
CELERY_BROKER_URL = os.getenv("CELERY_BROKER_URL") or _get_isolated_redis_url(1)
CELERY_RESULT_BACKEND = os.getenv("CELERY_RESULT_BACKEND") or _get_isolated_redis_url(2)

# Time limits
TASK_TIME_LIMIT = int(os.getenv("CELERY_TASK_TIME_LIMIT", "600"))
TASK_SOFT_TIME_LIMIT = int(os.getenv("CELERY_TASK_SOFT_TIME_LIMIT", "300"))
RESULT_EXPIRES = int(os.getenv("CELERY_RESULT_EXPIRES", "86400"))

# Initialize Celery app
celery_app = Celery("wallet_management_tasks")

# Configure Celery
celery_app.conf.update(
    broker_url=CELERY_BROKER_URL,
    result_backend=CELERY_RESULT_BACKEND,
    # Serialization security
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    # Timezone & Scheduling
    timezone="UTC",
    enable_utc=True,
    # Worker execution & reliability
    task_track_started=True,
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=1,
    result_expires=RESULT_EXPIRES,
    task_time_limit=TASK_TIME_LIMIT,
    task_soft_time_limit=TASK_SOFT_TIME_LIMIT,
    # Autodiscover background tasks modules
    include=[
        "app.jobs.daily_summary",
        "app.jobs.monthly_reminders",
        "app.jobs.excel_import",
        "app.jobs.notifications",
        "app.jobs.analytics",
    ],
    # Default and routed queues
    task_default_queue="default",
    task_routes={
        "app.jobs.excel_import.*": {"queue": "imports"},
        "app.jobs.daily_summary.*": {"queue": "scheduled"},
        "app.jobs.monthly_reminders.*": {"queue": "scheduled"},
        "app.jobs.notifications.*": {"queue": "notifications"},
        "app.jobs.analytics.*": {"queue": "default"},
    },
    # Celery Beat Scheduled Jobs (migrated from APScheduler)
    beat_schedule={
        "daily-financial-summary": {
            "task": "app.jobs.daily_summary.generate_daily_summaries_task",
            "schedule": crontab(hour=23, minute=59),
            "options": {"queue": "scheduled"},
        },
        "monthly-payment-reminders": {
            "task": "app.jobs.monthly_reminders.generate_monthly_reminders_task",
            "schedule": crontab(day_of_month=1, hour=0, minute=5),
            "options": {"queue": "scheduled"},
        },
    },
)

# Explicitly load tasks to register decorators
import app.jobs  # noqa: F401, E402


# Task execution timers for structured logging
_task_start_times: dict[str, float] = {}


@task_prerun.connect
def on_task_prerun(task_id, task, args, kwargs, **_):
    _task_start_times[task_id] = time.perf_counter()
    # Mask any sensitive keys if present in kwargs
    safe_kwargs = {
        k: ("***" if "password" in k.lower() or "token" in k.lower() or "secret" in k.lower() else v)
        for k, v in kwargs.items()
    }
    logger.info(
        "Celery task started: %s[id=%s] args=%s kwargs=%s",
        task.name,
        task_id,
        args,
        safe_kwargs,
    )


@task_postrun.connect
def on_task_postrun(task_id, task, state, **_):
    start = _task_start_times.pop(task_id, None)
    duration_str = f" in {(time.perf_counter() - start) * 1000:.2f}ms" if start else ""
    logger.info(
        "Celery task completed: %s[id=%s] state=%s%s",
        task.name,
        task_id,
        state,
        duration_str,
    )


@task_failure.connect
def on_task_failure(task_id, exception, args, kwargs, traceback, einfo, **_):
    _task_start_times.pop(task_id, None)
    logger.error(
        "Celery task failed: [id=%s] error=%s",
        task_id,
        str(exception),
        exc_info=einfo,
    )


@task_retry.connect
def on_task_retry(request, reason, einfo, **_):
    logger.warning(
        "Celery task retrying: %s[id=%s] retries=%d reason=%s",
        request.task,
        request.id,
        request.retries,
        str(reason),
    )
