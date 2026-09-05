import uuid
from decimal import Decimal

from sqlalchemy import String, Integer, Numeric, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class CustomerTier(Base):
    __tablename__ = "customer_tiers"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    rank: Mapped[int] = mapped_column(Integer, nullable=False)
    base_discount_ceiling_pct: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)

    customers: Mapped[list["Customer"]] = relationship(back_populates="tier")


class Customer(Base):
    __tablename__ = "customers"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    tier_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("customer_tiers.id"), nullable=False)
    currency: Mapped[str] = mapped_column(String(10), nullable=False, default="INR")

    tier: Mapped[CustomerTier] = relationship(back_populates="customers")
