from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, computed_field


def _format_decimal(value: Decimal) -> str:
    return format(value, "f")


class SavingsGoalCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    target_amount: Decimal = Field(gt=0)
    target_date: date | None = None


class SavingsGoalUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    target_amount: Decimal | None = Field(default=None, gt=0)
    target_date: date | None = None
    status: Literal["active", "completed"] | None = None


class SavingsContributionCreate(BaseModel):
    amount: Decimal = Field(gt=0)
    action: Literal["add", "withdraw"]


class SavingsGoalResponse(BaseModel):
    model_config = ConfigDict(
        from_attributes=True,
        json_encoders={Decimal: _format_decimal},
    )

    id: int
    user_id: int
    name: str
    target_amount: Decimal
    current_amount: Decimal
    target_date: date | None
    status: str
    date_created: datetime

    @computed_field
    @property
    def progress_percentage(self) -> Decimal:
        if not self.target_amount:
            return Decimal("0.00")
        return self.current_amount / self.target_amount * Decimal("100")
