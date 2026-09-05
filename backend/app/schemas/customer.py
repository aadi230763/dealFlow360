import uuid
from decimal import Decimal

from pydantic import BaseModel, EmailStr


class CustomerTierBase(BaseModel):
    name: str
    rank: int
    base_discount_ceiling_pct: Decimal


class CustomerTierCreate(CustomerTierBase):
    pass


class CustomerTierUpdate(BaseModel):
    name: str | None = None
    rank: int | None = None
    base_discount_ceiling_pct: Decimal | None = None


class CustomerTierOut(CustomerTierBase):
    id: uuid.UUID
    model_config = {"from_attributes": True}


class CustomerBase(BaseModel):
    name: str
    email: EmailStr
    tier_id: uuid.UUID
    currency: str = "INR"


class CustomerCreate(CustomerBase):
    pass


class CustomerUpdate(BaseModel):
    name: str | None = None
    email: EmailStr | None = None
    tier_id: uuid.UUID | None = None
    currency: str | None = None


class CustomerOut(CustomerBase):
    id: uuid.UUID
    model_config = {"from_attributes": True}
