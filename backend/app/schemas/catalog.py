import uuid
from decimal import Decimal

from pydantic import BaseModel


class CategoryBase(BaseModel):
    name: str
    default_discount_ceiling_pct: Decimal


class CategoryCreate(CategoryBase):
    pass


class CategoryUpdate(BaseModel):
    name: str | None = None
    default_discount_ceiling_pct: Decimal | None = None


class CategoryOut(CategoryBase):
    id: uuid.UUID
    model_config = {"from_attributes": True}


class ProductVariantBase(BaseModel):
    attribute_name: str
    value: str
    price_delta: Decimal = Decimal("0")


class ProductVariantCreate(ProductVariantBase):
    pass


class ProductVariantOut(ProductVariantBase):
    id: uuid.UUID
    model_config = {"from_attributes": True}


class ProductBase(BaseModel):
    name: str
    sku: str
    category_id: uuid.UUID
    unit: str = "each"
    list_price: Decimal
    unit_cost: Decimal
    tax_pct: Decimal = Decimal("0")
    description: str | None = None
    is_promoted: bool = False
    is_active: bool = True
    is_subscription: bool = False
    recurring_interval: str | None = None


class ProductCreate(ProductBase):
    variants: list[ProductVariantCreate] = []


class ProductUpdate(BaseModel):
    name: str | None = None
    sku: str | None = None
    category_id: uuid.UUID | None = None
    unit: str | None = None
    list_price: Decimal | None = None
    unit_cost: Decimal | None = None
    tax_pct: Decimal | None = None
    description: str | None = None
    is_promoted: bool | None = None
    is_active: bool | None = None
    is_subscription: bool | None = None
    recurring_interval: str | None = None


class ProductOut(ProductBase):
    id: uuid.UUID
    variants: list[ProductVariantOut] = []
    quantity_on_hand: int = 0
    model_config = {"from_attributes": True}
