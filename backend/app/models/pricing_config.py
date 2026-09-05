import uuid
from decimal import Decimal

from sqlalchemy import String, Numeric, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class PriceList(Base):
    __tablename__ = "price_lists"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    tier_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("customer_tiers.id"), nullable=False)
    currency: Mapped[str] = mapped_column(String(10), nullable=False, default="INR")

    items: Mapped[list["PriceListItem"]] = relationship(
        back_populates="price_list", cascade="all, delete-orphan"
    )


class PriceListItem(Base):
    __tablename__ = "price_list_items"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    price_list_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("price_lists.id"), nullable=False)
    product_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("products.id"), nullable=False)
    price: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)

    price_list: Mapped[PriceList] = relationship(back_populates="items")

    __table_args__ = (UniqueConstraint("price_list_id", "product_id", name="uq_price_list_product"),)


class CategoryTierCeiling(Base):
    """Resolution order: this table -> Category.default_discount_ceiling_pct -> CustomerTier.base_discount_ceiling_pct."""

    __tablename__ = "category_tier_ceilings"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    tier_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("customer_tiers.id"), nullable=False)
    category_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("categories.id"), nullable=False)
    ceiling_pct: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)

    __table_args__ = (UniqueConstraint("tier_id", "category_id", name="uq_tier_category_ceiling"),)
