import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import String, DateTime, Enum
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class Role(str, enum.Enum):
    ADMIN = "ADMIN"
    SALES_REP = "SALES_REP"
    SALES_MANAGER = "SALES_MANAGER"
    FINANCE = "FINANCE"
    # Owns warehouse stock levels and the manual fulfillment split -- who ships what from
    # which warehouse. Distinct from SALES_MANAGER (who owns discount/risk approvals).
    SHIPMENT_MANAGER = "SHIPMENT_MANAGER"


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[Role] = mapped_column(Enum(Role, name="role"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
