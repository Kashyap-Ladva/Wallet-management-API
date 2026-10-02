from pydantic import BaseModel, ConfigDict
from datetime import datetime

class UserCreate(BaseModel):
    name: str
    phone: str
    email: str
    currency: str
    date_created: datetime | None = None


class UserUpdate(BaseModel):
    name: str | None = None
    phone: str | None = None
    email: str | None = None
    currency: str | None = None
    date_created: datetime | None = None


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    currency: str
    phone: str
    email: str
    date_created: datetime
