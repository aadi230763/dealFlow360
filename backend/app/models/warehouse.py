import uuid
from decimal import Decimal

from sqlalchemy import String, Integer, Numeric, Boolean, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class Warehouse(Base):
    __tablename__ = "warehouses"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    code: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    shipping_cost_weight: Mapped[Decimal] = mapped_column(Numeric(6, 2), nullable=False, default=Decimal("1"))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    stock_levels: Mapped[list["StockLevel"]] = relationship(back_populates="warehouse")


class StockLevel(Base):
    __tablename__ = "stock_levels"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    warehouse_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("warehouses.id"), nullable=False)
    product_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("products.id"), nullable=False)
    on_hand: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    reserved: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    reorder_point: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    warehouse: Mapped[Warehouse] = relationship(back_populates="stock_levels")

    __table_args__ = (UniqueConstraint("warehouse_id", "product_id", name="uq_warehouse_product"),)
