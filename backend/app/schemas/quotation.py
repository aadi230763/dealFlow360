import uuid
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel

from app.models.quotation import LineType, QuotationStatus
from app.schemas.risk import RiskOut


class QuotationLineIn(BaseModel):
    product_id: uuid.UUID
    variant_id: uuid.UUID | None = None
    line_type: LineType = LineType.ONE_TIME
    qty: int = 1
    discount_pct: Decimal = Decimal("0")
    subscription_plan_id: uuid.UUID | None = None
    start_date: date | None = None


class QuotationPreviewRequest(BaseModel):
    customer_id: uuid.UUID
    lines: list[QuotationLineIn]


class LinePricingOut(BaseModel):
    product_id: uuid.UUID
    product_name: str
    variant_id: uuid.UUID | None
    line_type: str
    qty: int
    unit_price: Decimal
    gross: Decimal
    discount_pct: Decimal
    discount_amount: Decimal
    net: Decimal
    tax_amount: Decimal
    unit_cost: Decimal
    cost_total: Decimal
    margin_amount: Decimal
    margin_pct: Decimal
    category_id: uuid.UUID
    ceiling_pct: Decimal
    overage_pct: Decimal
    weight: Decimal


class QuotationPricingOut(BaseModel):
    lines: list[LinePricingOut]
    subtotal: Decimal
    discount_total: Decimal
    tax_total: Decimal
    net_total: Decimal
    grand_total: Decimal
    margin_amount: Decimal
    margin_pct: Decimal
    explanations: list[str]


class QuotationPreviewOut(QuotationPricingOut):
    risk: RiskOut


class QuotationCreate(BaseModel):
    customer_id: uuid.UUID
    lines: list[QuotationLineIn]


class QuotationLinesUpdate(BaseModel):
    lines: list[QuotationLineIn]


class QuotationLineOut(BaseModel):
    id: uuid.UUID
    product_id: uuid.UUID
    variant_id: uuid.UUID | None
    line_type: LineType
    qty: int
    unit_price: Decimal
    unit_cost: Decimal
    discount_pct: Decimal
    subscription_plan_id: uuid.UUID | None
    start_date: date | None
    computed: dict
    model_config = {"from_attributes": True}


class QuotationOut(BaseModel):
    id: uuid.UUID
    number: str
    customer_id: uuid.UUID
    owner_user_id: uuid.UUID
    status: QuotationStatus
    currency: str
    subtotal: Decimal
    discount_total: Decimal
    tax_total: Decimal
    grand_total: Decimal
    margin_amount: Decimal
    margin_pct: Decimal
    blended_score: Decimal
    peak_overage: Decimal
    erosion_amount: Decimal
    created_at: datetime
    updated_at: datetime
    last_activity_at: datetime
    lines: list[QuotationLineOut]
    model_config = {"from_attributes": True}


class QuotationListItem(BaseModel):
    id: uuid.UUID
    number: str
    customer_id: uuid.UUID
    customer_name: str
    tier_name: str
    owner_user_id: uuid.UUID
    owner_name: str
    status: QuotationStatus
    grand_total: Decimal
    margin_pct: Decimal
    blended_score: Decimal
    peak_overage: Decimal
    required_roles: list[str] = []
    created_at: datetime
    last_activity_at: datetime


class QuotationStatusUpdate(BaseModel):
    status: QuotationStatus
