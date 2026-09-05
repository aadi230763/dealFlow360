from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, get_db
from app.models.audit import AuditEvent
from app.models.user import User
from app.schemas.audit import AuditEventOut

router = APIRouter(prefix="/api/audit-events", tags=["audit"])


@router.get("", response_model=list[AuditEventOut])
def list_audit_events(
    entity_type: str | None = Query(None),
    entity_id: str | None = Query(None),
    limit: int = Query(50, le=200),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> list[AuditEvent]:
    q = db.query(AuditEvent)
    if entity_type is not None:
        q = q.filter(AuditEvent.entity_type == entity_type)
    if entity_id is not None:
        q = q.filter(AuditEvent.entity_id == entity_id)
    return q.order_by(AuditEvent.created_at.desc()).limit(limit).all()
