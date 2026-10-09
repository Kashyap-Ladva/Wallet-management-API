from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


def _format_decimal(value: Decimal) -> str:
    return format(value, "f")


class RecurringPaymentCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    amount: Decimal = Field(gt=0)
    category: str = Field(min_length=1, max_length=100)
    due_day: int = Field(ge=1, le=31)
    frequency: Literal["monthly"] = "monthly"
    active: bool = True


class RecurringPaymentUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    amount: Decimal | None = Field(default=None, gt=0)
    category: str | None = Field(default=None, min_length=1, max_length=100)
    due_day: int | None = Field(default=None, ge=1, le=31)
    frequency: Literal["monthly"] | None = None
    active: bool | None = None


class RecurringPaymentResponse(BaseModel):
    model_config = ConfigDict(
        from_attributes=True,
        json_encoders={Decimal: _format_decimal},
    )

    id: int
    user_id: int
    name: str
    amount: Decimal
    category: str
    due_day: int
    frequency: str
    active: bool
    date_created: datetime
