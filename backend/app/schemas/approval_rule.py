import uuid
from decimal import Decimal

from pydantic import BaseModel


class ApprovalRuleBase(BaseModel):
    name: str
    level: int
    min_blended: Decimal | None = None
    min_peak: Decimal | None = None
    min_erosion_amount: Decimal | None = None
    required_roles: list[str]
    sequence: int
    is_active: bool = True


class ApprovalRuleCreate(ApprovalRuleBase):
    pass


class ApprovalRuleUpdate(BaseModel):
    name: str | None = None
    level: int | None = None
    min_blended: Decimal | None = None
    min_peak: Decimal | None = None
    min_erosion_amount: Decimal | None = None
    required_roles: list[str] | None = None
    sequence: int | None = None
    is_active: bool | None = None


class ApprovalRuleOut(ApprovalRuleBase):
    id: uuid.UUID
    model_config = {"from_attributes": True}
