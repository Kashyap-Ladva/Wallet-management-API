from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel, ConfigDict


def _format_decimal(value: Decimal) -> str:
    return format(value, "f")


class DailySummary(BaseModel):
    model_config = ConfigDict(json_encoders={Decimal: _format_decimal})

    income: Decimal
    expense: Decimal
    net: Decimal
    transaction_count: int
    category_breakdown: dict[str, Decimal]
    mini_wallet_breakdown: dict[str, Decimal]


class MonthlySummary(BaseModel):
    model_config = ConfigDict(json_encoders={Decimal: _format_decimal})

    total_income: Decimal
    total_expense: Decimal
    net: Decimal
    transaction_count: int
    category_breakdown: dict[str, Decimal]
    mini_wallet_breakdown: dict[str, Decimal]


class CategorySummary(BaseModel):
    model_config = ConfigDict(json_encoders={Decimal: _format_decimal})

    category: str
    total: Decimal


class MiniWalletSummary(BaseModel):
    model_config = ConfigDict(json_encoders={Decimal: _format_decimal})

    mini_wallet_id: int
    name: str
    total: Decimal


class ChartData(BaseModel):
    model_config = ConfigDict(json_encoders={Decimal: _format_decimal})

    labels: list[str]
    values: list[Decimal]
