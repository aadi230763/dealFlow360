import uuid

from sqlalchemy.orm import Session

from app.models.audit import AuditEvent
from app.models.user import User


def log_event(
    db: Session,
    *,
    entity_type: str,
    entity_id: str,
    action: str,
    actor: User | None,
    payload: dict | None = None,
) -> AuditEvent:
    event = AuditEvent(
        id=uuid.uuid4(),
        entity_type=entity_type,
        entity_id=str(entity_id),
        actor_user_id=actor.id if actor else None,
        actor_label=actor.email if actor else "system",
        action=action,
        payload=payload or {},
    )
    db.add(event)
    db.flush()
    return event
