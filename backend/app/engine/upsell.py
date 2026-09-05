"""Pure upsell ranking. No DB calls -- the API layer builds the hypothetical priced
quotations (one per candidate, via the untouched engine/pricing.price_quotation) and
hands the results here. This is the only place that ranks/filters suggestions, so a
number shown on a suggestion card can never diverge from what actually happens on add.
"""

import uuid
from dataclasses import dataclass
from decimal import Decimal


@dataclass
class PairingCandidate:
    suggested_product_id: uuid.UUID
    product_name: str
    is_promoted: bool
    co_purchase_score: Decimal
    min_margin_pct: Decimal
    suggested_line_margin_pct: Decimal  # the candidate's own margin, from price_quotation on a qty=1/0%-discount line
    margin_delta: Decimal  # order margin_amount with the line added, minus order margin_amount without it
    new_grand_total: Decimal
    reason: str


@dataclass
class Suggestion:
    product_id: uuid.UUID
    product_name: str
    is_promoted: bool
    co_purchase_score: Decimal
    margin_delta: Decimal
    new_grand_total: Decimal
    reason: str


def suggest(candidates: list[PairingCandidate], dismissed: set[uuid.UUID]) -> list[Suggestion]:
    eligible = [
        c
        for c in candidates
        if c.suggested_product_id not in dismissed and c.suggested_line_margin_pct >= c.min_margin_pct
    ]
    # Rank by co_purchase_score; promoted products break ties at equal score.
    eligible.sort(key=lambda c: (-c.co_purchase_score, 0 if c.is_promoted else 1))
    return [
        Suggestion(
            product_id=c.suggested_product_id,
            product_name=c.product_name,
            is_promoted=c.is_promoted,
            co_purchase_score=c.co_purchase_score,
            margin_delta=c.margin_delta,
            new_grand_total=c.new_grand_total,
            reason=c.reason,
        )
        for c in eligible
    ]
