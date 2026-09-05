"""Pure risk scoring. Consumes the per-line breakdown that engine/pricing.py already
computes (overage points and net-value weight per line) -- no new DB access, no
duplicated math. This is what proves the score on screen is real: every number here
traces straight back to a line the rep can see.
"""

from dataclasses import dataclass, field
from decimal import Decimal

from app.engine.pricing import QuotationPricing


@dataclass
class LineRiskBreakdown:
    product_name: str
    ceiling_pct: Decimal
    discount_pct: Decimal
    overage_pct: Decimal
    weight: Decimal
    contribution: Decimal


@dataclass
class RiskResult:
    blended: Decimal
    peak: Decimal
    erosion: Decimal
    per_line_breakdown: list[LineRiskBreakdown] = field(default_factory=list)


def compute_risk(pricing: QuotationPricing) -> RiskResult:
    breakdown: list[LineRiskBreakdown] = []
    blended = Decimal("0")
    peak = Decimal("0")
    erosion = Decimal("0")

    for line in pricing.lines:
        contribution = line.overage_pct * line.weight
        blended += contribution
        peak = max(peak, line.overage_pct)
        erosion += (line.overage_pct / Decimal("100")) * line.gross

        breakdown.append(
            LineRiskBreakdown(
                product_name=line.product_name,
                ceiling_pct=line.ceiling_pct,
                discount_pct=line.discount_pct,
                overage_pct=line.overage_pct,
                weight=line.weight,
                contribution=contribution,
            )
        )

    return RiskResult(
        blended=blended.quantize(Decimal("0.01")),
        peak=peak.quantize(Decimal("0.01")),
        erosion=erosion.quantize(Decimal("0.01")),
        per_line_breakdown=breakdown,
    )
