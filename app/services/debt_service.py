from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Debt, DebtRepayment


def _get_debt(db: Session, user_id: int, debt_id: int) -> Debt | None:
    return db.scalar(
        select(Debt).where(Debt.id == debt_id, Debt.user_id == user_id)
    )


def _set_status(debt: Debt) -> None:
    if debt.remaining_amount == 0:
        debt.status = "settled"
    elif debt.remaining_amount < debt.amount:
        debt.status = "partially_paid"
    else:
        debt.status = "pending"


def create_debt(db: Session, user_id: int, payload: dict) -> Debt:
    debt = Debt(
        user_id=user_id,
        remaining_amount=payload["amount"],
        **payload,
    )
    db.add(debt)
    db.commit()
    db.refresh(debt)
    return debt


def list_debts(db: Session, user_id: int) -> list[Debt]:
    return list(
        db.scalars(
            select(Debt)
            .where(Debt.user_id == user_id)
            .order_by(Debt.date.desc(), Debt.id.desc())
        )
    )


def update_debt(
    db: Session,
    user_id: int,
    debt_id: int,
    updates: dict,
) -> Debt | None:
    debt = _get_debt(db, user_id, debt_id)
    if debt is None:
        return None
    if updates.get("amount") is not None:
        paid = debt.amount - debt.remaining_amount
        new_amount = Decimal(updates["amount"])
        if new_amount < paid:
            raise ValueError("Amount cannot be less than repayments already recorded")
        debt.amount = new_amount
        debt.remaining_amount = new_amount - paid
    for field, value in updates.items():
        if field == "amount" or (
            value is None and field not in {"due_date", "notes"}
        ):
            continue
        if field == "person":
            value = value.strip()
        setattr(debt, field, value)
    _set_status(debt)
    db.commit()
    db.refresh(debt)
    return debt


def record_repayment(
    db: Session,
    user_id: int,
    debt_id: int,
    payload: dict,
) -> DebtRepayment | None:
    debt = db.scalar(
        select(Debt)
        .where(Debt.id == debt_id, Debt.user_id == user_id)
        .with_for_update()
    )
    if debt is None:
        return None
    amount = Decimal(payload["amount"])
    if amount > debt.remaining_amount:
        raise ValueError("Repayment exceeds the remaining amount")

    repayment = DebtRepayment(debt_id=debt.id, **payload)
    debt.remaining_amount -= amount
    _set_status(debt)
    db.add(repayment)
    db.commit()
    db.refresh(repayment)
    return repayment


def delete_debt(db: Session, user_id: int, debt_id: int) -> bool:
    debt = _get_debt(db, user_id, debt_id)
    if debt is None:
        return False
    db.delete(debt)
    db.commit()
    return True
