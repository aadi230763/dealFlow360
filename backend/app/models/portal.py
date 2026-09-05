import enum
import uuid
from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy import String, DateTime, Date, Numeric, ForeignKey, Enum
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class PortalToken(Base):
    """A random opaque secret, hashed at rest -- never a JWT. Scoped to exactly one
    quotation, so a leaked token can't be walked to see other customers' deals."""

    __tablename__ = "portal_tokens"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    quotation_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("quotations.id"), nullable=False)
    customer_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("customers.id"), nullable=False)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )


class NegotiationType(str, enum.Enum):
    COMMENT = "COMMENT"
    CHANGE_REQUEST = "CHANGE_REQUEST"
    COUNTER_DISCOUNT = "COUNTER_DISCOUNT"


class NegotiationStatus(str, enum.Enum):
    PENDING = "PENDING"
    ACCEPTED = "ACCEPTED"
    COUNTERED = "COUNTERED"
    DECLINED = "DECLINED"
    ACKNOWLEDGED = "ACKNOWLEDGED"


class NegotiationRequest(Base):
    __tablename__ = "negotiation_requests"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    quotation_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("quotations.id"), nullable=False)
    # SET NULL, not a hard-blocking FK: quotation lines are deleted and recreated (new ids)
    # on every reprice (`_apply_lines`), so a comment tied to a line must be able to outlive
    # that line's id rather than fail the reprice outright.
    line_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("quotation_lines.id", ondelete="SET NULL"), nullable=True
    )
    type: Mapped[NegotiationType] = mapped_column(Enum(NegotiationType, name="negotiation_type"), nullable=False)
    message: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    proposed_discount_pct: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)
    requested_delivery_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[NegotiationStatus] = mapped_column(
        Enum(NegotiationStatus, name="negotiation_status"), nullable=False, default=NegotiationStatus.PENDING
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    responded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    responder_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    response_message: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    # The rep's own counter-number when they respond with action="counter" -- distinct from
    # `proposed_discount_pct` above, which is always the customer's ask. Without this the
    # rep's counter only ever lived in free-text `response_message` and never reached the
    # portal at all.
    counter_discount_pct: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)
