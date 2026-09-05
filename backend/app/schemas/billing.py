import uuid
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel

from app.models.billing import BillingScheduleStatus, InvoiceStatus, InvoiceType
from app.models.subscription_plan import Interval


class PeriodOccurrenceOut(BaseModel):
    period_start: date
    period_end: date
    amount: Decimal


class SubscriptionListItem(BaseModel):
    schedule_id: uuid.UUID
    customer_name: str
    plan_name: str
    interval: Interval
    next_billing_date: date
    status: BillingScheduleStatus


class OneTimeLineOut(BaseModel):
    product_name: str
    qty: int
    amount: Decimal


class SubscriptionDetailOut(BaseModel):
    schedule_id: uuid.UUID
    order_id: uuid.UUID
    order_number: str
    customer_name: str
    plan_name: str
    interval: Interval
    interval_count: int
    qty: int
    amount: Decimal
    next_billing_date: date
    status: BillingScheduleStatus
    proration_policy: str
    cancellation_policy: str
    one_time_lines: list[OneTimeLineOut]
    upcoming: list[PeriodOccurrenceOut]


class SubscriptionChangeRequest(BaseModel):
    new_qty: int
    preview: bool = False


class ProrationPreviewOut(BaseModel):
    old_qty: int
    new_qty: int
    delta_amount: Decimal
    is_credit: bool
    days_remaining: int
    days_in_period: int
    new_period_amount: Decimal
    summary: str


class InvoiceListItem(BaseModel):
    id: uuid.UUID
    number: str
    customer_name: str
    amount: Decimal
    tax: Decimal
    status: InvoiceStatus
    type: InvoiceType
    due_date: date


class PaymentOut(BaseModel):
    id: uuid.UUID
    amount: Decimal
    method: str
    reference: str | None
    received_at: datetime
    model_config = {"from_attributes": True}


class InvoiceDetailOut(BaseModel):
    id: uuid.UUID
    number: str
    order_id: uuid.UUID
    order_number: str
    customer_name: str
    type: InvoiceType
    amount: Decimal
    tax: Decimal
    status: InvoiceStatus
    issue_date: date
    due_date: date
    period_start: date | None
    period_end: date | None
    payments: list[PaymentOut]
    stage: str


class PaymentCreate(BaseModel):
    amount: Decimal
    method: str
    reference: str | None = None
