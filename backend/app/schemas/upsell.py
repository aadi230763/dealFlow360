import uuid
from decimal import Decimal

from pydantic import BaseModel


class SuggestionOut(BaseModel):
    product_id: uuid.UUID
    product_name: str
    is_promoted: bool
    co_purchase_score: Decimal
    margin_delta: Decimal
    new_grand_total: Decimal
    reason: str
