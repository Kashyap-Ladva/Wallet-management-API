from datetime import date
from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user
from app.core.rate_limit import rate_limit_read
from app.database import get_db
from app.models import User
from app.services import analytics_service, cache_service

router = APIRouter(tags=["analytics"], dependencies=[Depends(rate_limit_read)])


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
async def get_daily_analytics(
    date_value: date | None = Query(default=None, alias="date"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    target_date = date_value or date.today()
    cache_key = cache_service.build_cache_key(
        current_user.id,
        "daily",
        date=str(target_date),
    )

    cached_result = await cache_service.get_cached(cache_key)
    if cached_result is not None:
        return cached_result

    summary = analytics_service.get_daily_summary(db, current_user.id, target_date)
    formatted = _format_daily(summary)
    await cache_service.set_cached(
        cache_key,
        formatted,
        ttl=cache_service.ANALYTICS_DAILY_CACHE_TTL,
    )
    return formatted


@router.get("/analytics/monthly")
async def get_monthly_analytics(
    year: int = Query(...),
    month: int = Query(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    cache_key = cache_service.build_cache_key(
        current_user.id,
        "monthly",
        year=year,
        month=month,
    )

    cached_result = await cache_service.get_cached(cache_key)
    if cached_result is not None:
        return cached_result

    summary = analytics_service.get_monthly_summary(db, current_user.id, year, month)
    formatted = _format_monthly(summary)
    await cache_service.set_cached(
        cache_key,
        formatted,
        ttl=cache_service.ANALYTICS_MONTHLY_CACHE_TTL,
    )
    return formatted


@router.get("/analytics/yearly")
async def get_yearly_analytics(
    year: int = Query(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    cache_key = cache_service.build_cache_key(
        current_user.id,
        "yearly",
        year=year,
    )

    cached_result = await cache_service.get_cached(cache_key)
    if cached_result is not None:
        return cached_result

    yearly = analytics_service.get_yearly_summary(db, current_user.id, year)
    formatted = {
        key: _format_monthly(value)
        for key, value in yearly.items()
    }
    await cache_service.set_cached(
        cache_key,
        formatted,
        ttl=cache_service.ANALYTICS_MONTHLY_CACHE_TTL,
    )
    return formatted


@router.get("/analytics/mini-wallets")
async def get_mini_wallet_comparison(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    cache_key = cache_service.build_cache_key(current_user.id, "mini-wallets")
    cached_result = await cache_service.get_cached(cache_key)
    if cached_result is not None:
        return cached_result

    rows = analytics_service.get_mini_wallet_summary(db, current_user.id)
    formatted = [
        {"mini_wallet_id": row["mini_wallet_id"], "name": row["name"], "total": f"{row['total']:.2f}"}
        for row in rows
    ]
    await cache_service.set_cached(
        cache_key,
        formatted,
        ttl=cache_service.ANALYTICS_DEFAULT_CACHE_TTL,
    )
    return formatted


@router.get("/analytics/categories")
async def get_category_comparison(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    cache_key = cache_service.build_cache_key(current_user.id, "categories")
    cached_result = await cache_service.get_cached(cache_key)
    if cached_result is not None:
        return cached_result

    rows = analytics_service.get_category_summary(db, current_user.id)
    formatted = [
        {"category": row["category"], "total": f"{row['total']:.2f}"}
        for row in rows
    ]
    await cache_service.set_cached(
        cache_key,
        formatted,
        ttl=cache_service.ANALYTICS_DEFAULT_CACHE_TTL,
    )
    return formatted


@router.get("/analytics/expenses/pie")
async def get_expense_pie_chart(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    cache_key = cache_service.build_cache_key(current_user.id, "expenses_pie")
    cached_result = await cache_service.get_cached(cache_key)
    if cached_result is not None:
        return cached_result

    rows = analytics_service.get_expense_pie_data(db, current_user.id)
    formatted = {
        "labels": rows["labels"],
        "values": [f"{value:.2f}" for value in rows["values"]],
    }
    await cache_service.set_cached(
        cache_key,
        formatted,
        ttl=cache_service.ANALYTICS_DEFAULT_CACHE_TTL,
    )
    return formatted


@router.get("/analytics/expenses/bar")
async def get_expense_bar_chart(
    year: int | None = Query(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    cache_key = cache_service.build_cache_key(
        current_user.id,
        "expenses_bar",
        year=year or "all",
    )
    cached_result = await cache_service.get_cached(cache_key)
    if cached_result is not None:
        return cached_result

    rows = analytics_service.get_expense_bar_data(db, current_user.id, year)
    formatted = {
        "labels": rows["labels"],
        "values": [f"{value:.2f}" for value in rows["values"]],
    }
    await cache_service.set_cached(
        cache_key,
        formatted,
        ttl=cache_service.ANALYTICS_DEFAULT_CACHE_TTL,
    )
    return formatted
