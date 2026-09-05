import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel

from app.models.approval_request import ApprovalRequestStatus


class LineRiskBreakdownOut(BaseModel):
    product_name: str
    ceiling_pct: Decimal
    discount_pct: Decimal
    overage_pct: Decimal
    weight: Decimal
    contribution: Decimal


class ApprovalStepOut(BaseModel):
    rule_id: str
    rule_name: str
    level: int
    required_role: str
    sequence: int
    reason: str


class RiskOut(BaseModel):
    blended: Decimal
    peak: Decimal
    erosion: Decimal
    breakdown: list[LineRiskBreakdownOut]
    chain: list[ApprovalStepOut]
    chain_explanations: list[str]


class ApprovalActionRequest(BaseModel):
    action: str  # "approve" | "reject" | "return_for_revision"
    comment: str | None = None


class ApprovalRequestOut(BaseModel):
    id: uuid.UUID
    quotation_id: uuid.UUID
    level: int
    required_role: str
    status: ApprovalRequestStatus
    sequence: int
    acted_by_user_id: uuid.UUID | None
    acted_by_name: str | None = None
    acted_at: datetime | None
    comment: str | None
    snapshot: dict
    created_at: datetime
    model_config = {"from_attributes": True}


class ApprovalInboxItem(BaseModel):
    approval_request_id: uuid.UUID
    quotation_id: uuid.UUID
    quotation_number: str
    customer_name: str
    owner_name: str
    grand_total: Decimal
    blended_score: Decimal
    peak_overage: Decimal
    erosion_amount: Decimal
    sequence: int
    level: int
    created_at: datetime


class ApprovalListItem(BaseModel):
    """Screen 5 (Approvals List): every quotation that ever went through routing,
    not just what's actionable by the current viewer -- actionability is enforced
    at the act() endpoint, not by hiding rows here."""

    quotation_id: uuid.UUID
    quotation_number: str
    customer_name: str
    tier_name: str
    grand_total: Decimal
    blended_score: Decimal
    peak_overage: Decimal
    required_roles: list[str]
    overall_status: str  # "PENDING" | "RETURNED" | "APPROVED" | "REJECTED"
    stage: str
    assigned_to: str
    created_at: datetime
