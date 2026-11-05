import calendar
from datetime import date, datetime, timezone
import logging

from sqlalchemy import select
from sqlalchemy.exc import DBAPIError, OperationalError
from sqlalchemy.orm import Session

from app.core.celery_app import celery_app
from app.database import get_task_db
from app.models import Notification, RecurringPayment

logger = logging.getLogger("app.jobs.monthly_reminders")


def generate_monthly_reminders(
    db: Session,
    reminder_month: date | None = None,
) -> int:
    target = reminder_month or datetime.now(timezone.utc).date()
    period = f"{target.year:04d}-{target.month:02d}"
    month_end = calendar.monthrange(target.year, target.month)[1]
    payments = list(
        db.scalars(
            select(RecurringPayment)
            .where(RecurringPayment.active.is_(True))
            .order_by(RecurringPayment.user_id, RecurringPayment.id)
        )
    )
    created = 0
    for payment in payments:
        try:
            with db.begin_nested():
                dedupe_key = f"recurring-payment:{payment.id}:{period}"
                existing = db.scalar(
                    select(Notification.id).where(
                        Notification.user_id == payment.user_id,
                        Notification.dedupe_key == dedupe_key,
                    )
                )
                if existing is not None:
                    continue

                due_date = date(target.year, target.month, min(payment.due_day, month_end))
                message = (
                    f"{payment.name} payment of {payment.amount} is due "
                    f"on {due_date.isoformat()}."
                )
                db.add(
                    Notification(
                        user_id=payment.user_id,
                        kind="recurring_payment_reminder",
                        dedupe_key=dedupe_key,
                        recurring_payment_id=payment.id,
                        message=message,
                        payload={
                            "recurring_payment_id": payment.id,
                            "name": payment.name,
                            "amount": str(payment.amount),
                            "category": payment.category,
                            "due_date": due_date.isoformat(),
                            "period": period,
                        },
                    )
                )
                created += 1
            db.commit()
        except Exception as exc:
            logger.error(
                "Error generating monthly reminder for payment %d: %s",
                payment.id,
                exc,
            )
            db.rollback()
            continue

    return created


def run_monthly_reminders_job() -> int:
    with get_task_db() as db:
        return generate_monthly_reminders(db)


@celery_app.task(
    name="app.jobs.monthly_reminders.generate_monthly_reminders_task",
    bind=True,
    max_retries=3,
    default_retry_delay=60,
    autoretry_for=(OperationalError, DBAPIError),
    retry_backoff=True,
    retry_jitter=True,
)
def generate_monthly_reminders_task(self, target_date_str: str | None = None) -> dict:
    """
    Celery task to generate monthly recurring payment reminders.
    Idempotent and protected against transient database connection failures.
    """
    target = date.fromisoformat(target_date_str) if target_date_str else None
    with get_task_db() as db:
        count = generate_monthly_reminders(db, target)
        resolved_date = target or datetime.now(timezone.utc).date()
        return {
            "status": "SUCCESS",
            "reminders_generated": count,
            "period": f"{resolved_date.year:04d}-{resolved_date.month:02d}",
        }
