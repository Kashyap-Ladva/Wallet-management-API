from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel, ConfigDict


from app.schema.common import DecimalStr


class DailySummary(BaseModel):
    income: DecimalStr
    expense: DecimalStr
    net: DecimalStr
    transaction_count: int
    category_breakdown: dict[str, DecimalStr]
    mini_wallet_breakdown: dict[str, DecimalStr]


class MonthlySummary(BaseModel):
    total_income: DecimalStr
    total_expense: DecimalStr
    net: DecimalStr
    transaction_count: int
    category_breakdown: dict[str, DecimalStr]
    mini_wallet_breakdown: dict[str, DecimalStr]


class CategorySummary(BaseModel):
    category: str
    total: DecimalStr


class MiniWalletSummary(BaseModel):
    mini_wallet_id: int
    name: str
    total: DecimalStr


class ChartData(BaseModel):
    labels: list[str]
    values: list[DecimalStr]
