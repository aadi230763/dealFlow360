import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, get_db
from app.models.notification import Notification
from app.models.quotation import Quotation
from app.models.user import User
from app.schemas.notification import NotificationOut

router = APIRouter(prefix="/api/notifications", tags=["notifications"])


def _to_out(notification: Notification, quotation_number: str | None) -> NotificationOut:
    return NotificationOut(
        id=notification.id,
        event_type=notification.event_type,
        message=notification.message,
        quotation_id=notification.quotation_id,
        quotation_number=quotation_number,
        read_at=notification.read_at,
        created_at=notification.created_at,
    )


@router.get("", response_model=list[NotificationOut])
def list_notifications(
    unread_only: bool = Query(False),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[NotificationOut]:
    q = db.query(Notification).filter(Notification.user_id == user.id)
    if unread_only:
        q = q.filter(Notification.read_at.is_(None))
    notifications = q.order_by(Notification.created_at.desc()).limit(100).all()

    quotation_ids = {n.quotation_id for n in notifications if n.quotation_id}
    numbers = (
        {q.id: q.number for q in db.query(Quotation).filter(Quotation.id.in_(quotation_ids)).all()}
        if quotation_ids
        else {}
    )
    return [_to_out(n, numbers.get(n.quotation_id)) for n in notifications]


@router.post("/{notification_id}/read", response_model=NotificationOut)
def mark_read(
    notification_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> NotificationOut:
    notification = db.get(Notification, notification_id)
    if notification is None or notification.user_id != user.id:
        # 404 rather than 403 -- a notification id that isn't yours shouldn't confirm
        # to the caller that it exists at all.
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Notification not found")
    if notification.read_at is None:
        notification.read_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(notification)
    quotation = db.get(Quotation, notification.quotation_id) if notification.quotation_id else None
    return _to_out(notification, quotation.number if quotation else None)


@router.post("/read-all", status_code=status.HTTP_204_NO_CONTENT)
def mark_all_read(db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> None:
    db.query(Notification).filter(Notification.user_id == user.id, Notification.read_at.is_(None)).update(
        {"read_at": datetime.now(timezone.utc)}
    )
    db.commit()
