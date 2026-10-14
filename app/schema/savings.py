from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, computed_field


from app.schema.common import DecimalStr


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
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    name: str
    target_amount: DecimalStr
    current_amount: DecimalStr
    target_date: date | None
    status: str
    date_created: datetime

    @computed_field
    @property
    def progress_percentage(self) -> DecimalStr:
        if not self.target_amount:
            return Decimal("0.00")
        return self.current_amount / self.target_amount * Decimal("100")
