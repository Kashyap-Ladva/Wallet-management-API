from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


class NotificationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    kind: str
    message: str
    payload: dict[str, Any]
    read_at: datetime | None
    date_created: datetime
