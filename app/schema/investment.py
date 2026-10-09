from datetime import date as Date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


def _format_decimal(value: Decimal) -> str:
    return format(value, "f")


class InvestmentCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    amount: Decimal = Field(gt=0)
    investment_type: str = Field(min_length=1, max_length=100)
    date: Date
    notes: str | None = None


class InvestmentUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    amount: Decimal | None = Field(default=None, gt=0)
    investment_type: str | None = Field(default=None, min_length=1, max_length=100)
    date: Date | None = None
    notes: str | None = None


class InvestmentResponse(BaseModel):
    model_config = ConfigDict(
        from_attributes=True,
        json_encoders={Decimal: _format_decimal},
    )

    id: int
    user_id: int
    name: str
    amount: Decimal
    investment_type: str
    date: Date
    notes: str | None
    date_created: datetime
