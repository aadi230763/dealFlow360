import uuid
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel

from app.models.portal import NegotiationStatus, NegotiationType

# Deliberately its own schema tree, never reused from the internal quotation schemas --
# no cost, unit_cost, margin, ceiling, overage, weight, or risk field exists anywhere
# below. If a field needs to appear on the portal it has to be added here explicitly.


class PortalLineOut(BaseModel):
    id: uuid.UUID
    product_name: str
    qty: int
    unit_price: Decimal
    discount_pct: Decimal
    net: Decimal
    tax_amount: Decimal
    line_total: Decimal
    comment: str | None = None


class PortalQuotationOut(BaseModel):
    number: str
    customer_name: str
    status: str
    currency: str
    lines: list[PortalLineOut]
    subtotal: Decimal
    discount_total: Decimal
    tax_total: Decimal
    grand_total: Decimal
    latest_counter_discount_pct: Decimal | None = None
    latest_requested_delivery_date: date | None = None
    expires_at: datetime


class SendQuotationOut(BaseModel):
    url: str
    expires_at: datetime


class PortalNegotiateRequest(BaseModel):
    line_comments: dict[uuid.UUID, str] = {}
    proposed_discount_pct: Decimal | None = None
    requested_delivery_date: date | None = None


class PortalConfirmOut(BaseModel):
    status: str  # "PENDING_APPROVAL" | "CONFIRMED"
    message: str


class NegotiationRequestOut(BaseModel):
    id: uuid.UUID
    quotation_id: uuid.UUID
    line_id: uuid.UUID | None
    line_product_name: str | None
    type: NegotiationType
    message: str | None
    proposed_discount_pct: Decimal | None
    requested_delivery_date: date | None
    status: NegotiationStatus
    created_at: datetime
    responded_at: datetime | None
    responder_name: str | None
    response_message: str | None


class NegotiationRespondRequest(BaseModel):
    action: str  # "accept" | "counter" | "decline"
    response_message: str | None = None
