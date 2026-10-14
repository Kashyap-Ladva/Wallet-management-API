from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.schema.common import DecimalStr

BudgetPeriod = Literal["daily", "monthly"]


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
    model_config = ConfigDict(from_attributes=True)

    id: int
    super_wallet_id: int
    name: str
    period: str
    amount: DecimalStr
    category: str | None = None
    date_created: datetime


class BudgetStatusResponse(BaseModel):
    target: DecimalStr
    spent: DecimalStr
    remaining: DecimalStr
    percentage_used: DecimalStr
    exceeded: bool
