import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel


class StalledDealOut(BaseModel):
    quotation_id: uuid.UUID
    number: str
    customer_name: str
    owner_name: str
    idle_days: int
    value_at_risk: Decimal
    flagged_at: datetime
    last_action: str | None = None


class DiscountAnomalyOut(BaseModel):
    quotation_id: uuid.UUID
    number: str
    customer_name: str
    rep_id: uuid.UUID
    rep_name: str
    discount_pct: Decimal
    baseline_pct: Decimal
    z_score: Decimal | None
    method: str
    flagged_at: datetime
    last_action: str | None = None


class DeliverySlippageOut(BaseModel):
    fulfillment_id: uuid.UUID
    quotation_id: uuid.UUID
    number: str
    customer_name: str
    days_late: int
    backorder_qty: int
    flagged_at: datetime
    last_action: str | None = None


class DashboardHealthOut(BaseModel):
    stalled: list[StalledDealOut]
    anomalies: list[DiscountAnomalyOut]
    slippage: list[DeliverySlippageOut]


class RepDiscountPoint(BaseModel):
    rep_name: str
    discount_pct: Decimal
    is_outlier: bool


class MarginTrendPoint(BaseModel):
    period: str  # "2026-08" style month bucket
    margin_pct: Decimal


class DashboardMetricsOut(BaseModel):
    quotes_created: int
    avg_approval_time_hours: Decimal | None
    top_upsold_product: str | None
    win_rate_pct: Decimal
    discount_by_rep: list[RepDiscountPoint]
    margin_trend: list[MarginTrendPoint]


class ReportFilters(BaseModel):
    period_days: int | None = None
    owner_user_id: uuid.UUID | None = None
    approval_status: str | None = None
    product_id: uuid.UUID | None = None


class ReportOut(BaseModel):
    quotes_created: int
    avg_approval_time_hours: Decimal | None
    top_upsold_product: str | None
    total_pipeline_value: Decimal


class NudgeActionOut(BaseModel):
    quotation_id: uuid.UUID
    action: str  # "nudge" | "escalate"
