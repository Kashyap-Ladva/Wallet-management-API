from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


BudgetPeriod = Literal["daily", "monthly"]


def _format_decimal(value: Decimal) -> str:
    return format(value, "f")


class BudgetCreate(BaseModel):
    name: str
    period: BudgetPeriod
    amount: Decimal = Field(gt=0)
    category: str | None = None


class BudgetUpdate(BaseModel):
    name: str | None = None
    period: BudgetPeriod | None = None
    amount: Decimal | None = Field(default=None, gt=0)
    category: str | None = None


class BudgetResponse(BaseModel):
    model_config = ConfigDict(
        from_attributes=True,
        json_encoders={Decimal: _format_decimal},
    )

    id: int
    super_wallet_id: int
    name: str
    period: str
    amount: Decimal
    category: str | None = None
    date_created: datetime


class BudgetStatusResponse(BaseModel):
    model_config = ConfigDict(json_encoders={Decimal: _format_decimal})

    target: Decimal
    spent: Decimal
    remaining: Decimal
    percentage_used: Decimal
    exceeded: bool
