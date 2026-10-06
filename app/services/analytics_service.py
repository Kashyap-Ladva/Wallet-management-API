from __future__ import annotations

from calendar import month_abbr, month_name
from datetime import date
from decimal import Decimal

from sqlalchemy import case, func
from sqlalchemy.orm import Session

from app.models import MWallet, SWallet, Transaction


def _decimal(value) -> Decimal:
    if value is None:
        return Decimal("0.00")
    return Decimal(str(value))


def _user_transaction_query(db: Session, user_id: int):
    return (
        db.query(Transaction)
        .join(SWallet, SWallet.id == Transaction.super_wallet_id)
        .filter(SWallet.user_id == user_id)
    )


def get_daily_summary(db: Session, user_id: int, target_date: date):
    query = _user_transaction_query(db, user_id).filter(
        func.date(Transaction.date_created) == target_date
    )

    income = (
        query.filter(Transaction.type == "income")
        .with_entities(func.coalesce(func.sum(Transaction.amount), Decimal("0.00")))
        .scalar()
        or Decimal("0.00")
    )
    expense = (
        query.filter(Transaction.type == "expense")
        .with_entities(func.coalesce(func.sum(Transaction.amount), Decimal("0.00")))
        .scalar()
        or Decimal("0.00")
    )
    category_rows = (
        query.filter(Transaction.type == "expense")
        .with_entities(
            Transaction.category,
            func.coalesce(func.sum(Transaction.amount), Decimal("0.00")).label("total"),
        )
        .group_by(Transaction.category)
        .all()
    )
    mini_wallet_rows = (
        query.filter(Transaction.type == "expense")
        .join(MWallet, MWallet.id == Transaction.mini_wallet_id)
        .with_entities(
            MWallet.name,
            func.coalesce(func.sum(Transaction.amount), Decimal("0.00")).label("total"),
        )
        .group_by(MWallet.id, MWallet.name)
        .all()
    )

    category_breakdown = {
        category: _decimal(total)
        for category, total in category_rows
    }
    mini_wallet_breakdown = {
        name: _decimal(total)
        for name, total in mini_wallet_rows
    }

    return {
        "income": _decimal(income),
        "expense": _decimal(expense),
        "net": _decimal(income) - _decimal(expense),
        "transaction_count": query.count(),
        "category_breakdown": category_breakdown,
        "mini_wallet_breakdown": mini_wallet_breakdown,
    }


def get_monthly_summary(db: Session, user_id: int, year: int, month: int):
    query = _user_transaction_query(db, user_id)
    if db.bind and db.bind.dialect.name == "postgresql":
        query = query.filter(
            func.extract("year", Transaction.date_created) == year,
            func.extract("month", Transaction.date_created) == month,
        )
    else:
        query = query.filter(
            func.strftime("%Y", Transaction.date_created) == str(year),
            func.strftime("%m", Transaction.date_created) == f"{month:02d}",
        )

    income = (
        query.filter(Transaction.type == "income")
        .with_entities(func.coalesce(func.sum(Transaction.amount), Decimal("0.00")))
        .scalar()
        or Decimal("0.00")
    )
    expense = (
        query.filter(Transaction.type == "expense")
        .with_entities(func.coalesce(func.sum(Transaction.amount), Decimal("0.00")))
        .scalar()
        or Decimal("0.00")
    )
    category_rows = (
        query.filter(Transaction.type == "expense")
        .with_entities(
            Transaction.category,
            func.coalesce(func.sum(Transaction.amount), Decimal("0.00")).label("total"),
        )
        .group_by(Transaction.category)
        .all()
    )
    mini_wallet_rows = (
        query.filter(Transaction.type == "expense")
        .join(MWallet, MWallet.id == Transaction.mini_wallet_id)
        .with_entities(
            MWallet.name,
            func.coalesce(func.sum(Transaction.amount), Decimal("0.00")).label("total"),
        )
        .group_by(MWallet.id, MWallet.name)
        .all()
    )

    return {
        "total_income": _decimal(income),
        "total_expense": _decimal(expense),
        "net": _decimal(income) - _decimal(expense),
        "transaction_count": query.count(),
        "category_breakdown": {
            category: _decimal(total)
            for category, total in category_rows
        },
        "mini_wallet_breakdown": {
            name: _decimal(total)
            for name, total in mini_wallet_rows
        },
    }


def get_yearly_summary(db: Session, user_id: int, year: int):
    summary = {}
    for month_number in range(1, 13):
        monthly = get_monthly_summary(db, user_id, year, month_number)
        summary[month_name[month_number]] = {
            "total_income": monthly["total_income"],
            "total_expense": monthly["total_expense"],
            "net": monthly["net"],
            "transaction_count": monthly["transaction_count"],
            "category_breakdown": monthly["category_breakdown"],
            "mini_wallet_breakdown": monthly["mini_wallet_breakdown"],
        }
    return summary


def get_mini_wallet_summary(db: Session, user_id: int):
    rows = (
        _user_transaction_query(db, user_id)
        .filter(Transaction.type == "expense")
        .join(MWallet, MWallet.id == Transaction.mini_wallet_id)
        .with_entities(
            MWallet.id,
            MWallet.name,
            func.coalesce(func.sum(Transaction.amount), Decimal("0.00")).label("total"),
        )
        .group_by(MWallet.id, MWallet.name)
        .order_by(MWallet.id)
        .all()
    )
    return [
        {"mini_wallet_id": mini_wallet_id, "name": name, "total": _decimal(total)}
        for mini_wallet_id, name, total in rows
    ]


def get_category_summary(db: Session, user_id: int):
    rows = (
        _user_transaction_query(db, user_id)
        .filter(Transaction.type == "expense")
        .with_entities(
            Transaction.category,
            func.coalesce(func.sum(Transaction.amount), Decimal("0.00")).label("total"),
        )
        .group_by(Transaction.category)
        .order_by(Transaction.category)
        .all()
    )
    return [
        {"category": category, "total": _decimal(total)}
        for category, total in rows
    ]


def get_expense_pie_data(db: Session, user_id: int):
    rows = get_category_summary(db, user_id)
    return {
        "labels": [item["category"] for item in rows],
        "values": [item["total"] for item in rows],
    }


def get_expense_bar_data(db: Session, user_id: int, year: int | None = None):
    year = year or date.today().year
    values: list[Decimal] = []
    for month_number in range(1, 13):
        month_summary = get_monthly_summary(db, user_id, year, month_number)
        values.append(month_summary["total_expense"])
    return {
        "labels": [month_abbr[index] for index in range(1, 13)],
        "values": values,
    }
