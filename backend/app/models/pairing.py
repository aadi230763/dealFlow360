import uuid
from decimal import Decimal

from sqlalchemy import Numeric, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class ProductPairing(Base):
    __tablename__ = "product_pairings"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    product_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("products.id"), nullable=False)
    suggested_product_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("products.id"), nullable=False)
    co_purchase_score: Mapped[Decimal] = mapped_column(Numeric(4, 3), nullable=False)
    min_margin_pct: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
