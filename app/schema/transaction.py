from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class TransactionCreate(BaseModel):
    amount: float = Field(gt=0)
    type: Literal["income", "expense"]
    category: str
    description: str | None = None


class TransactionUpdate(BaseModel):
    amount: float | None = Field(default=None, gt=0)
    type: Literal["income", "expense"] | None = None
    category: str | None = None
    description: str | None = None


class TransactionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    wallet_id: int
    amount: float
    type: Literal["income", "expense"]
    category: str
    description: str | None = None
