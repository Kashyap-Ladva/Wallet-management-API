from datetime import datetime
from typing import Any, Optional
from pydantic import BaseModel, ConfigDict


class TaskStatusResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    task_id: str
    status: str
    result: Optional[Any] = None
    error: Optional[str] = None


class AsyncImportCreatedResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    import_id: str
    task_id: str
    status: str = "PENDING"
    message: str = "Import queued for processing"
    file_sha256: str


class ImportJobStatusResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    import_id: str
    task_id: Optional[str] = None
    status: str
    total_rows: int = 0
    imported_count: int = 0
    file_sha256: Optional[str] = None
    error_details: Optional[Any] = None
    date_created: datetime
    date_completed: Optional[datetime] = None

