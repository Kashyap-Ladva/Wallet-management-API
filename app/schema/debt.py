from datetime import date as Date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


def _format_decimal(value: Decimal) -> str:
    return format(value, "f")


DebtDirection = Literal["lent", "borrowed"]


class DebtCreate(BaseModel):
    person: str = Field(min_length=1, max_length=200)
    direction: DebtDirection
    amount: Decimal = Field(gt=0)
    date: Date
    due_date: Date | None = None
    notes: str | None = None


class DebtUpdate(BaseModel):
    person: str | None = Field(default=None, min_length=1, max_length=200)
    direction: DebtDirection | None = None
    amount: Decimal | None = Field(default=None, gt=0)
    date: Date | None = None
    due_date: Date | None = None
    notes: str | None = None


class DebtRepaymentCreate(BaseModel):
    amount: Decimal = Field(gt=0)
    date: Date
    notes: str | None = None


class DebtResponse(BaseModel):
    model_config = ConfigDict(
        from_attributes=True,
        json_encoders={Decimal: _format_decimal},
    )

    id: int
    user_id: int
    person: str
    direction: DebtDirection
    amount: Decimal
    remaining_amount: Decimal
    date: Date
    due_date: Date | None
    status: Literal["pending", "partially_paid", "settled"]
    notes: str | None
    date_created: datetime


class DebtRepaymentResponse(BaseModel):
    model_config = ConfigDict(
        from_attributes=True,
        json_encoders={Decimal: _format_decimal},
    )

    id: int
    debt_id: int
    amount: Decimal
    date: Date
    notes: str | None
