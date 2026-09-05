import enum
import uuid
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, Numeric, Enum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class FulfillmentStatus(str, enum.Enum):
    PLANNED = "PLANNED"
    ACCEPTED = "ACCEPTED"


class Fulfillment(Base):
    __tablename__ = "fulfillments"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    quotation_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("quotations.id"), nullable=False)
    status: Mapped[FulfillmentStatus] = mapped_column(
        Enum(FulfillmentStatus, name="fulfillment_status"), nullable=False, default=FulfillmentStatus.PLANNED
    )
    total_shipments: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    estimated_cost: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=Decimal("0"))
    is_manual_override: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    allocations: Mapped[list["FulfillmentAllocation"]] = relationship(
        back_populates="fulfillment", cascade="all, delete-orphan"
    )


class FulfillmentAllocation(Base):
    __tablename__ = "fulfillment_allocations"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    fulfillment_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("fulfillments.id"), nullable=False)
    quotation_line_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("quotation_lines.id"), nullable=False)
    warehouse_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("warehouses.id"), nullable=True)
    qty: Mapped[int] = mapped_column(Integer, nullable=False)
    is_backorder: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    shipped_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    fulfillment: Mapped[Fulfillment] = relationship(back_populates="allocations")
