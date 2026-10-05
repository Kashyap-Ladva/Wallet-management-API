from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

TransactionType = Literal["income", "expense"]


class TransactionCreate(BaseModel):
    amount: Decimal = Field(gt=0)
    type: TransactionType
    category: str
    description: str | None = None
    date_created: datetime | None = None
    modeofpayment: str
    proof: str | None = None


class TransactionUpdate(BaseModel):
    amount: Decimal | None = Field(default=None, gt=0)
    type: TransactionType | None = None
    category: str | None = None
    description: str | None = None
    date_created: datetime | None = None
    modeofpayment: str | None = None
    proof: str | None = None


class TransactionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    mini_wallet_id: int
    super_wallet_id: int
    amount: Decimal
    type: TransactionType
    category: str
    description: str | None = None
    date_created: datetime
    modeofpayment: str
    proof: str | None = None


class TransactionFilter(BaseModel):
    date_from: datetime | None = None
    date_to: datetime | None = None
    type: TransactionType | None = None
    category: str | None = None
    modeofpayment: str | None = None
    mini_wallet_id: int | None = None
    limit: int = 50
    offset: int = 0
