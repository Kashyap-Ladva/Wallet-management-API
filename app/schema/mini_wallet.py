from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict

class MWalletCreate(BaseModel):
    name: str
    modeofpayment: str
    date_created: datetime | None = None


class MWalletUpdate(BaseModel):
    name: str | None = None
    modeofpayment: str | None = None
    date_created: datetime | None = None



class MWalletResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    super_wallet_id: int
    name: str
    modeofpayment: str
    balance: Decimal
    date_created: datetime
