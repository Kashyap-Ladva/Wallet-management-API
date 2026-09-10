from pydantic import BaseModel


class WalletCreate(BaseModel):
    name: str
    currency: str


class WalletUpdate(BaseModel):
    name: str | None = None
    currency: str | None = None


class WalletResponse(BaseModel):
    id: int
    name: str
    currency: str
    balance: float
