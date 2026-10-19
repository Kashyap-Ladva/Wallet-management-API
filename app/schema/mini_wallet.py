from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, field_validator


from app.schema.common import DecimalStr


class MWalletCreate(BaseModel):
    name: str | None = None
    modeofpayment: str
    date_created: datetime | None = None

    @field_validator("modeofpayment")
    @classmethod
    def validate_modeofpayment(cls, v: str) -> str:
        if not v or not str(v).strip():
            raise ValueError("modeofpayment cannot be empty")
        return " ".join(str(v).strip().split()).upper()


class MWalletUpdate(BaseModel):
    name: str | None = None
    modeofpayment: str | None = None
    date_created: datetime | None = None

    @field_validator("modeofpayment")
    @classmethod
    def validate_modeofpayment(cls, v: str | None) -> str | None:
        if v is not None:
            if not str(v).strip():
                raise ValueError("modeofpayment cannot be empty")
            return " ".join(str(v).strip().split()).upper()
        return v



class MWalletResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    super_wallet_id: int
    name: str
    modeofpayment: str
    balance: DecimalStr
    date_created: datetime
