import uuid
from decimal import Decimal

from pydantic import BaseModel


class ProductPairingBase(BaseModel):
    product_id: uuid.UUID
    suggested_product_id: uuid.UUID
    co_purchase_score: Decimal
    min_margin_pct: Decimal


class ProductPairingCreate(ProductPairingBase):
    pass


class ProductPairingUpdate(BaseModel):
    product_id: uuid.UUID | None = None
    suggested_product_id: uuid.UUID | None = None
    co_purchase_score: Decimal | None = None
    min_margin_pct: Decimal | None = None


class ProductPairingOut(ProductPairingBase):
    id: uuid.UUID
    model_config = {"from_attributes": True}
