import uuid
from datetime import datetime

from pydantic import BaseModel


class AuditEventOut(BaseModel):
    id: uuid.UUID
    entity_type: str
    entity_id: str
    actor_label: str
    action: str
    payload: dict
    created_at: datetime
    model_config = {"from_attributes": True}
