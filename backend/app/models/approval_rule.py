import uuid
from decimal import Decimal

from sqlalchemy import String, Integer, Numeric, Boolean
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class ApprovalRule(Base):
    __tablename__ = "approval_rules"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    level: Mapped[int] = mapped_column(Integer, nullable=False)
    min_blended: Mapped[Decimal | None] = mapped_column(Numeric(6, 2), nullable=True)
    min_peak: Mapped[Decimal | None] = mapped_column(Numeric(6, 2), nullable=True)
    min_erosion_amount: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    required_roles: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
