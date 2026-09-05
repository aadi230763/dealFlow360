import uuid
from decimal import Decimal

from pydantic import BaseModel


class CeilingCellOut(BaseModel):
    tier_id: uuid.UUID
    tier_name: str
    category_id: uuid.UUID
    category_name: str
    ceiling_pct: Decimal
    is_override: bool


class CeilingMatrixOut(BaseModel):
    cells: list[CeilingCellOut]


class CeilingUpsert(BaseModel):
    tier_id: uuid.UUID
    category_id: uuid.UUID
    ceiling_pct: Decimal


class PriceListItemIn(BaseModel):
    product_id: uuid.UUID
    price: Decimal


class PriceListItemOut(PriceListItemIn):
    id: uuid.UUID
    model_config = {"from_attributes": True}


class PriceListBase(BaseModel):
    name: str
    tier_id: uuid.UUID
    currency: str = "INR"


class PriceListCreate(PriceListBase):
    items: list[PriceListItemIn] = []


class PriceListOut(PriceListBase):
    id: uuid.UUID
    items: list[PriceListItemOut] = []
    model_config = {"from_attributes": True}
