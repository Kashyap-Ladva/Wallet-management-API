import logging
import os
from typing import Optional

from celery.result import AsyncResult
from fastapi import APIRouter, Depends, HTTPException, status
import redis
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.celery_app import celery_app
from app.core.dependencies import get_current_user
from app.database import get_db
from app.models import ImportJob, User
from app.schema.celery_tasks import TaskStatusResponse

logger = logging.getLogger("app.routers.tasks")

router = APIRouter(prefix="/tasks", tags=["tasks"])


def record_task_ownership(task_id: str, user_id: int) -> None:
    """Record task ownership in Redis with 24-hour expiration."""
    redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    try:
        r = redis.Redis.from_url(redis_url, decode_responses=True, socket_timeout=0.2)
        r.set(f"celery_task_owner:{task_id}", str(user_id), ex=86400)
    except Exception as exc:
        logger.debug("Redis task ownership record skipped: %s", exc)


def get_task_owner(task_id: str, db: Session) -> Optional[int]:
    """Retrieve owner user ID for a task from database or Redis."""
    # Check import_jobs table first (fastest, most reliable)
    job = db.scalar(select(ImportJob).where(ImportJob.task_id == task_id))
    if job:
        return job.user_id

    # Fallback to Redis
    redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    try:
        r = redis.Redis.from_url(redis_url, decode_responses=True, socket_timeout=0.2)
        owner = r.get(f"celery_task_owner:{task_id}")
        if owner is not None:
            return int(owner)
    except Exception as exc:
        logger.debug("Redis task owner lookup skipped: %s", exc)

    return None


@router.get("/{task_id}", response_model=TaskStatusResponse)
def get_task_status(
    task_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Retrieve task status by task ID.
    Enforces strict user ownership: users can only check their own tasks.
    Never exposes internal exception traces.
    """
    owner_id = get_task_owner(task_id, db)
    if owner_id is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task not found",
        )

    if owner_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden",
        )

    # Inspect task state via Celery result backend or DB fallback
    state = "PENDING"
    task_res = None
    task_err = None

    try:
        result = AsyncResult(task_id, app=celery_app)
        state = result.state
        if state == "SUCCESS":
            raw_res = result.result
            if isinstance(raw_res, (dict, list, str, int, float, bool)):
                task_res = raw_res
            else:
                task_res = {"status": "SUCCESS"}
        elif state == "FAILURE":
            task_err = "Task execution encountered an error"
        elif state == "RETRY":
            task_err = "Task is currently retrying"
    except Exception as exc:
        logger.debug("Celery backend query error for task %s: %s", task_id, exc)
        # Database fallback for ImportJob
        job = db.scalar(select(ImportJob).where(ImportJob.task_id == task_id))
        if job:
            state = job.status
            if job.status == "FAILED" and job.error_details:
                task_err = "Import processing encountered errors"

    # Normalize state string
    if state == "PENDING":
        task_status = "PENDING"
    elif state == "STARTED":
        task_status = "PROCESSING"
    elif state in ("SUCCESS", "COMPLETED"):
        task_status = "COMPLETED"
    elif state in ("FAILURE", "FAILED"):
        task_status = "FAILED"
        if not task_err:
            task_err = "Task execution failed"
    elif state == "RETRY":
        task_status = "RETRY"
        task_err = "Task is retrying"
    else:
        task_status = state

    return TaskStatusResponse(
        task_id=task_id,
        status=task_status,
        result=task_res,
        error=task_err,
    )
