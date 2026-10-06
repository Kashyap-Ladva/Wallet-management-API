from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict


def _format_decimal(value: Decimal) -> str:
    return format(value, "f")


class SWalletCreate(BaseModel):
    name: str
    currency: str


class SWalletUpdate(BaseModel):
    name: str | None = None
    currency: str | None = None


class SWalletResponse(BaseModel):
    model_config = ConfigDict(
        from_attributes=True,
        json_encoders={Decimal: _format_decimal},
    )

    id: int
    user_id: int
    name: str
    currency: str
    modeofpayment: str
    total_balance: Decimal
    date_created: datetime
