from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict


def _format_decimal(value: Decimal) -> str:
    return format(value, "f")


class MWalletCreate(BaseModel):
    name: str
    modeofpayment: str
    date_created: datetime | None = None


class MWalletUpdate(BaseModel):
    name: str | None = None
    modeofpayment: str | None = None
    date_created: datetime | None = None



class MWalletResponse(BaseModel):
    model_config = ConfigDict(
        from_attributes=True,
        json_encoders={Decimal: _format_decimal},
    )

    id: int
    super_wallet_id: int
    name: str
    modeofpayment: str
    balance: Decimal
    date_created: datetime
