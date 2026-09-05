import uuid

from pydantic import BaseModel

from app.models.subscription_plan import Interval, ProrationPolicy


class SubscriptionPlanBase(BaseModel):
    name: str
    interval: Interval
    interval_count: int = 1
    proration_policy: ProrationPolicy
    cancellation_policy: str = "CREDIT_REMAINING"


class SubscriptionPlanCreate(SubscriptionPlanBase):
    pass


class SubscriptionPlanUpdate(BaseModel):
    name: str | None = None
    interval: Interval | None = None
    interval_count: int | None = None
    proration_policy: ProrationPolicy | None = None
    cancellation_policy: str | None = None


class SubscriptionPlanOut(SubscriptionPlanBase):
    id: uuid.UUID
    model_config = {"from_attributes": True}
