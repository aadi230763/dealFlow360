import uuid
from datetime import datetime

from pydantic import BaseModel


class NotificationOut(BaseModel):
    id: uuid.UUID
    event_type: str
    message: str
    quotation_id: uuid.UUID | None
    quotation_number: str | None = None
    read_at: datetime | None
    created_at: datetime
