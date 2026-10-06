from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user
from app.database import get_db
from app.models import User
from app.services import analytics_service

router = APIRouter(tags=["analytics"])


def _format_daily(summary: dict) -> dict:
    return {
        "income": f"{summary['income']:.2f}",
        "expense": f"{summary['expense']:.2f}",
        "net": f"{summary['net']:.2f}",
        "transaction_count": summary["transaction_count"],
        "category_breakdown": {
            key: f"{value:.2f}" for key, value in summary["category_breakdown"].items()
        },
        "mini_wallet_breakdown": {
            key: f"{value:.2f}" for key, value in summary["mini_wallet_breakdown"].items()
        },
    }


def _format_monthly(summary: dict) -> dict:
    return {
        "total_income": f"{summary['total_income']:.2f}",
        "total_expense": f"{summary['total_expense']:.2f}",
        "net": f"{summary['net']:.2f}",
        "transaction_count": summary["transaction_count"],
        "category_breakdown": {
            key: f"{value:.2f}" for key, value in summary["category_breakdown"].items()
        },
        "mini_wallet_breakdown": {
            key: f"{value:.2f}" for key, value in summary["mini_wallet_breakdown"].items()
        },
    }


@router.get("/analytics/daily")
def get_daily_analytics(
    date_value: date | None = Query(default=None, alias="date"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    target_date = date_value or date.today()
    summary = analytics_service.get_daily_summary(db, current_user.id, target_date)
    return _format_daily(summary)


@router.get("/analytics/monthly")
def get_monthly_analytics(
    year: int = Query(...),
    month: int = Query(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    summary = analytics_service.get_monthly_summary(db, current_user.id, year, month)
    return _format_monthly(summary)


@router.get("/analytics/yearly")
def get_yearly_analytics(
    year: int = Query(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    yearly = analytics_service.get_yearly_summary(db, current_user.id, year)
    return {
        key: _format_monthly(value)
        for key, value in yearly.items()
    }


@router.get("/analytics/mini-wallets")
def get_mini_wallet_comparison(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    rows = analytics_service.get_mini_wallet_summary(db, current_user.id)
    return [
        {"mini_wallet_id": row["mini_wallet_id"], "name": row["name"], "total": f"{row['total']:.2f}"}
        for row in rows
    ]


@router.get("/analytics/categories")
def get_category_comparison(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    rows = analytics_service.get_category_summary(db, current_user.id)
    return [
        {"category": row["category"], "total": f"{row['total']:.2f}"}
        for row in rows
    ]


@router.get("/analytics/expenses/pie")
def get_expense_pie_chart(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    rows = analytics_service.get_expense_pie_data(db, current_user.id)
    return {
        "labels": rows["labels"],
        "values": [f"{value:.2f}" for value in rows["values"]],
    }


@router.get("/analytics/expenses/bar")
def get_expense_bar_chart(
    year: int | None = Query(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    rows = analytics_service.get_expense_bar_data(db, current_user.id, year)
    return {
        "labels": rows["labels"],
        "values": [f"{value:.2f}" for value in rows["values"]],
    }
