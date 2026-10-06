from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models import Budget, SWallet, Transaction


def _as_decimal(value: Any) -> Decimal:
    if value is None:
        return Decimal("0.00")
    return Decimal(str(value))


def _get_super_wallet_for_user(db: Session, user_id: int) -> SWallet | None:
    return db.query(SWallet).filter(SWallet.user_id == user_id).first()


def _get_budget_for_user(db: Session, user_id: int, budget_id: int) -> Budget | None:
    return (
        db.query(Budget)
        .join(SWallet, SWallet.id == Budget.super_wallet_id)
        .filter(SWallet.user_id == user_id, Budget.id == budget_id)
        .first()
    )


def create_budget(db: Session, user_id: int, payload: dict) -> Budget:
    super_wallet = _get_super_wallet_for_user(db, user_id)
    if super_wallet is None:
        raise ValueError("Super wallet not found")
    period = str(payload.get("period") or "monthly").lower()
    if period not in {"daily", "monthly"}:
        raise ValueError("Budget period must be 'daily' or 'monthly'")

    budget = Budget(
        super_wallet_id=super_wallet.id,
        name=str(payload.get("name") or "Budget").strip(),
        period=period,
        amount=_as_decimal(payload.get("amount")),
        category=(payload.get("category") or "").strip() or None,
    )
    db.add(budget)
    db.commit()
    db.refresh(budget)
    return budget


def list_budgets_for_user(db: Session, user_id: int) -> list[Budget]:
    return (
        db.query(Budget)
        .join(SWallet, SWallet.id == Budget.super_wallet_id)
        .filter(SWallet.user_id == user_id)
        .order_by(Budget.id.desc())
        .all()
    )


def update_budget(db: Session, user_id: int, budget_id: int, updates: dict) -> Budget | None:
    budget = _get_budget_for_user(db, user_id, budget_id)
    if budget is None:
        return None
    for field, value in updates.items():
        if value is None:
            continue
        if field == "period":
            value = str(value).lower()
            if value not in {"daily", "monthly"}:
                raise ValueError("Budget period must be 'daily' or 'monthly'")
        if field == "amount":
            value = _as_decimal(value)
        if field == "name":
            value = str(value).strip()
        if field == "category":
            value = str(value).strip() or None
        setattr(budget, field, value)
    db.commit()
    db.refresh(budget)
    return budget


def delete_budget(db: Session, user_id: int, budget_id: int) -> bool:
    budget = _get_budget_for_user(db, user_id, budget_id)
    if budget is None:
        return False
    db.delete(budget)
    db.commit()
    return True


def get_budget_status(db: Session, user_id: int, budget_id: int) -> dict:
    budget = _get_budget_for_user(db, user_id, budget_id)
    if budget is None:
        raise ValueError("Budget not found")

    target = _as_decimal(budget.amount)
    spent = _get_budget_spent(db, budget)
    remaining = target - spent
    percentage_used = (spent / target * Decimal("100")) if target else Decimal("0.00")
    exceeded = spent > target

    return {
        "budget_id": budget.id,
        "name": budget.name,
        "target": _as_decimal(target),
        "spent": _as_decimal(spent),
        "remaining": _as_decimal(remaining),
        "percentage_used": _as_decimal(percentage_used),
        "exceeded": exceeded,
    }


def _get_budget_spent(db: Session, budget: Budget) -> Decimal:
    query = (
        db.query(Transaction)
        .filter(
            Transaction.super_wallet_id == budget.super_wallet_id,
            Transaction.type == "expense",
        )
    )

    if budget.category:
        query = query.filter(Transaction.category == budget.category)

    if budget.period == "daily":
        today = date.today()
        query = query.filter(
            Transaction.date_created >= datetime.combine(today, datetime.min.time()),
            Transaction.date_created < datetime.combine(today, datetime.max.time()),
        )
    else:
        latest = query.order_by(Transaction.date_created.desc()).first()
        if latest is not None:
            relevant_date = latest.date_created
            first_day = datetime(relevant_date.year, relevant_date.month, 1)
            if relevant_date.month == 12:
                next_month = datetime(relevant_date.year + 1, 1, 1)
            else:
                next_month = datetime(relevant_date.year, relevant_date.month + 1, 1)
            query = query.filter(
                Transaction.date_created >= first_day,
                Transaction.date_created < next_month,
            )
        else:
            today = date.today()
            first_day = datetime(today.year, today.month, 1)
            if today.month == 12:
                next_month = datetime(today.year + 1, 1, 1)
            else:
                next_month = datetime(today.year, today.month + 1, 1)
            query = query.filter(
                Transaction.date_created >= first_day,
                Transaction.date_created < next_month,
            )

    value = (
        query.with_entities(func.coalesce(func.sum(Transaction.amount), Decimal("0.00")))
        .scalar()
    )
    return _as_decimal(value)
