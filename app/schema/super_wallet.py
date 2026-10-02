from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict


class SWalletCreate(BaseModel):
    name: str
    currency: str
    modeofpayment: str
    date_created: datetime | None = None


class SWalletUpdate(BaseModel):
    name: str | None = None
    currency: str | None = None
    modeofpayment: str | None = None
    date_created: datetime | None = None


class SWalletResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    name: str
    currency: str
    modeofpayment: str
    total_balance: Decimal
    date_created: datetime
