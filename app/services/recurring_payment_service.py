from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import RecurringPayment


def _get_payment(
    db: Session,
    user_id: int,
    payment_id: int,
) -> RecurringPayment | None:
    return db.scalar(
        select(RecurringPayment).where(
            RecurringPayment.id == payment_id,
            RecurringPayment.user_id == user_id,
        )
    )


def create_payment(db: Session, user_id: int, payload: dict) -> RecurringPayment:
    payment = RecurringPayment(user_id=user_id, **payload)
    db.add(payment)
    db.commit()
    db.refresh(payment)
    return payment


def list_payments(db: Session, user_id: int) -> list[RecurringPayment]:
    return list(
        db.scalars(
            select(RecurringPayment)
            .where(RecurringPayment.user_id == user_id)
            .order_by(RecurringPayment.due_day, RecurringPayment.id)
        )
    )


def update_payment(
    db: Session,
    user_id: int,
    payment_id: int,
    updates: dict,
) -> RecurringPayment | None:
    payment = _get_payment(db, user_id, payment_id)
    if payment is None:
        return None
    if "frequency" in updates and updates["frequency"] != "monthly":
        raise ValueError("Only monthly recurring payments are supported")
    for field, value in updates.items():
        if value is None:
            continue
        if field in {"name", "category"}:
            value = value.strip()
        setattr(payment, field, value)
    db.commit()
    db.refresh(payment)
    return payment


def delete_payment(db: Session, user_id: int, payment_id: int) -> bool:
    payment = _get_payment(db, user_id, payment_id)
    if payment is None:
        return False
    db.delete(payment)
    db.commit()
    return True
