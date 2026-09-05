"""Centralized in-app notification dispatch. Routers never decide who gets notified or
what the message says -- they call `dispatch_event(db, event_type, context, quotation_id)`
with the same facts they already log to the audit trail, and every recipient-resolution
and message-rendering rule lives here in one table (RULES), not scattered across routers.

Reuses the existing SSE broadcaster (core/events.publish) rather than adding a second
transport: each created Notification fires one extra `notification_created` SSE event
carrying the recipient's user_id, so a connected client can tell whether a given
notification is meant for it. No DB dependency was added to core/events.py itself --
this module sits beside it and calls into it, same relationship core/audit.py already has.
"""

import uuid
from dataclasses import dataclass
from typing import Any, Callable

from sqlalchemy.orm import Session

from app.core.events import publish
from app.models.notification import Notification
from app.models.user import Role, User

RecipientResolver = Callable[[Session, dict[str, Any]], list[uuid.UUID]]
MessageRenderer = Callable[[dict[str, Any]], str]


@dataclass(frozen=True)
class NotificationRule:
    resolve_recipients: RecipientResolver
    render_message: MessageRenderer


def _users_with_role(db: Session, role: str) -> list[uuid.UUID]:
    try:
        role_enum = Role(role)
    except ValueError:
        return []
    return [u.id for u in db.query(User.id).filter(User.role == role_enum).all()]


def _owner(_db: Session, context: dict[str, Any]) -> list[uuid.UUID]:
    owner_id = context.get("owner_user_id")
    return [owner_id] if owner_id else []


def _role_recipients(db: Session, context: dict[str, Any]) -> list[uuid.UUID]:
    role = context.get("role")
    return _users_with_role(db, role) if role else []


# One entry per business event this system already knows how to raise (via the existing
# audit_events / SSE publish() call sites). Adding a new notifiable event means adding a
# row here and one `dispatch_event(...)` call at the point that already logs/publishes it
# -- never new recipient logic in the router itself.
RULES: dict[str, NotificationRule] = {
    "quotation_submitted_for_approval": NotificationRule(
        resolve_recipients=_role_recipients,
        render_message=lambda ctx: f"Quotation {ctx['number']} needs your approval.",
    ),
    "quotation_auto_approved": NotificationRule(
        resolve_recipients=_owner,
        render_message=lambda ctx: f"Quotation {ctx['number']} was auto-approved.",
    ),
    "quotation_routed_to_next_approver": NotificationRule(
        resolve_recipients=_role_recipients,
        render_message=lambda ctx: f"Quotation {ctx['number']} was routed to you for approval.",
    ),
    "quotation_approved": NotificationRule(
        resolve_recipients=_owner,
        render_message=lambda ctx: f"Quotation {ctx['number']} was approved.",
    ),
    "quotation_rejected": NotificationRule(
        resolve_recipients=_owner,
        render_message=lambda ctx: f"Quotation {ctx['number']} was rejected.",
    ),
    "quotation_returned_for_revision": NotificationRule(
        resolve_recipients=_owner,
        render_message=lambda ctx: f"Quotation {ctx['number']} was returned for revision.",
    ),
    "quotation_recomputed_reentered_approval": NotificationRule(
        resolve_recipients=_owner,
        render_message=lambda ctx: f"Quotation {ctx['number']} was recomputed and re-entered approval.",
    ),
    "negotiation_created": NotificationRule(
        resolve_recipients=_owner,
        render_message=lambda ctx: f"Customer submitted a negotiation request on {ctx['number']}.",
    ),
    "quotation_reentered_approval_from_portal": NotificationRule(
        resolve_recipients=_role_recipients,
        render_message=lambda ctx: f"Quotation {ctx['number']} re-entered approval after customer confirmation.",
    ),
}


def dispatch_event(
    db: Session,
    event_type: str,
    context: dict[str, Any],
    quotation_id: uuid.UUID | None,
) -> list[Notification]:
    rule = RULES.get(event_type)
    if rule is None:
        return []

    recipient_ids = {uid for uid in rule.resolve_recipients(db, context) if uid is not None}
    if not recipient_ids:
        return []

    message = rule.render_message(context)
    created: list[Notification] = []
    for user_id in recipient_ids:
        notification = Notification(
            id=uuid.uuid4(),
            user_id=user_id,
            event_type=event_type,
            message=message,
            quotation_id=quotation_id,
        )
        db.add(notification)
        created.append(notification)
    db.flush()

    for notification in created:
        publish(
            {
                "type": "notification_created",
                "user_id": str(notification.user_id),
                "notification_id": str(notification.id),
                "event_type": notification.event_type,
                "quotation_id": str(quotation_id) if quotation_id else None,
            }
        )
    return created
