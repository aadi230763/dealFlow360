import uuid
from decimal import Decimal

from pydantic import BaseModel


class WarehouseBase(BaseModel):
    name: str
    code: str
    shipping_cost_weight: Decimal = Decimal("1")
    is_active: bool = True


class WarehouseCreate(WarehouseBase):
    pass


class WarehouseUpdate(BaseModel):
    name: str | None = None
    code: str | None = None
    shipping_cost_weight: Decimal | None = None
    is_active: bool | None = None


class WarehouseOut(WarehouseBase):
    id: uuid.UUID
    model_config = {"from_attributes": True}


class StockLevelBase(BaseModel):
    warehouse_id: uuid.UUID
    product_id: uuid.UUID
    on_hand: int = 0
    reserved: int = 0
    reorder_point: int = 0


class StockLevelUpsert(BaseModel):
    on_hand: int
    reorder_point: int


class StockLevelOut(StockLevelBase):
    id: uuid.UUID
    model_config = {"from_attributes": True}
