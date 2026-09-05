import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel

from app.models.fulfillment import FulfillmentStatus


class FulfillmentAllocationOut(BaseModel):
    id: uuid.UUID
    quotation_line_id: uuid.UUID
    product_id: uuid.UUID
    product_name: str
    line_qty: int
    warehouse_id: uuid.UUID | None
    warehouse_name: str | None
    qty: int
    is_backorder: bool
    shipped_at: datetime | None
    model_config = {"from_attributes": True}


class FulfillmentOut(BaseModel):
    id: uuid.UUID
    quotation_id: uuid.UUID
    quotation_number: str
    customer_name: str
    status: FulfillmentStatus
    total_shipments: int
    estimated_cost: Decimal
    is_manual_override: bool
    explanations: list[str]
    allocations: list[FulfillmentAllocationOut]
    created_at: datetime


class FulfillmentListItem(BaseModel):
    fulfillment_id: uuid.UUID
    quotation_id: uuid.UUID
    order_number: str
    customer_name: str
    status_label: str
    warehouse_names: str


class OverrideAllocationIn(BaseModel):
    quotation_line_id: uuid.UUID
    warehouse_id: uuid.UUID
    qty: int


class OverrideRequest(BaseModel):
    allocations: list[OverrideAllocationIn]
