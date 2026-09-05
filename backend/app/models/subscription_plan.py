import enum
import uuid

from sqlalchemy import String, Integer, Enum
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class Interval(str, enum.Enum):
    MONTHLY = "MONTHLY"
    QUARTERLY = "QUARTERLY"
    YEARLY = "YEARLY"


class ProrationPolicy(str, enum.Enum):
    DAILY_PRORATE = "DAILY_PRORATE"
    FULL_PERIOD = "FULL_PERIOD"
    NONE = "NONE"


class SubscriptionPlan(Base):
    __tablename__ = "subscription_plans"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    interval: Mapped[Interval] = mapped_column(Enum(Interval, name="subscription_interval"), nullable=False)
    interval_count: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    proration_policy: Mapped[ProrationPolicy] = mapped_column(
        Enum(ProrationPolicy, name="proration_policy"), nullable=False
    )
    cancellation_policy: Mapped[str] = mapped_column(String(50), nullable=False, default="CREDIT_REMAINING")
