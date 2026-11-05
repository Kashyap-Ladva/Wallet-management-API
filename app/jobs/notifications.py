import logging
from sqlalchemy import select
from sqlalchemy.exc import DBAPIError, OperationalError

from app.core.celery_app import celery_app
from app.database import get_task_db
from app.models import Notification

logger = logging.getLogger("app.jobs.notifications")


@celery_app.task(
    name="app.jobs.notifications.dispatch_notification_task",
    bind=True,
    max_retries=3,
    default_retry_delay=15,
    autoretry_for=(OperationalError, DBAPIError),
    retry_backoff=True,
)
def dispatch_notification_task(
    self,
    user_id: int,
    kind: str,
    message: str,
    payload: dict,
    dedupe_key: str | None = None,
    recurring_payment_id: int | None = None,
) -> dict:
    """
    Asynchronously record and dispatch a user notification.
    Guarantees deduplication if dedupe_key is provided.
    """
    with get_task_db() as db:
        if dedupe_key:
            existing = db.scalar(
                select(Notification.id).where(
                    Notification.user_id == user_id,
                    Notification.dedupe_key == dedupe_key,
                )
            )
            if existing is not None:
                return {
                    "status": "SKIPPED",
                    "reason": "Duplicate notification",
                    "dedupe_key": dedupe_key,
                }

        notification = Notification(
            user_id=user_id,
            kind=kind,
            dedupe_key=dedupe_key or f"{kind}:{user_id}:{self.request.id}",
            message=message,
            payload=payload or {},
            recurring_payment_id=recurring_payment_id,
        )
        db.add(notification)
        db.commit()
        db.refresh(notification)

        logger.info(
            "Dispatched notification: id=%d, user_id=%d, kind=%s",
            notification.id,
            user_id,
            kind,
        )
        return {
            "status": "SUCCESS",
            "notification_id": notification.id,
            "user_id": user_id,
            "kind": kind,
        }


@celery_app.task(
    name="app.jobs.notifications.dispatch_bulk_notifications_task",
    bind=True,
    max_retries=3,
    default_retry_delay=30,
    autoretry_for=(OperationalError, DBAPIError),
    retry_backoff=True,
)
def dispatch_bulk_notifications_task(
    self,
    notifications_data: list[dict],
) -> dict:
    """
    Asynchronously process and insert a batch of notifications with savepoints.
    """
    created_count = 0
    with get_task_db() as db:
        for item in notifications_data:
            user_id = item.get("user_id")
            dedupe_key = item.get("dedupe_key")
            try:
                with db.begin_nested():
                    if dedupe_key:
                        existing = db.scalar(
                            select(Notification.id).where(
                                Notification.user_id == user_id,
                                Notification.dedupe_key == dedupe_key,
                            )
                        )
                        if existing is not None:
                            continue

                    notification = Notification(
                        user_id=user_id,
                        kind=item.get("kind", "general"),
                        dedupe_key=dedupe_key or f"bulk:{user_id}:{item.get('id', '')}",
                        message=item.get("message", ""),
                        payload=item.get("payload", {}),
                        recurring_payment_id=item.get("recurring_payment_id"),
                    )
                    db.add(notification)
                    created_count += 1
                db.commit()
            except Exception as exc:
                logger.error("Error creating bulk notification for user %s: %s", user_id, exc)
                db.rollback()
                continue

    return {"status": "SUCCESS", "created_count": created_count}

