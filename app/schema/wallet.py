from pydantic import BaseModel, ConfigDict


class WalletCreate(BaseModel):
    name: str
    currency: str


class WalletUpdate(BaseModel):
    name: str | None = None
    currency: str | None = None


class WalletResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    currency: str
    balance: float
