import calendar
from datetime import date, datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Notification, RecurringPayment


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
    return created


def run_monthly_reminders_job() -> int:
    from app.database import SessionLocal

    with SessionLocal() as db:
        return generate_monthly_reminders(db)
