"""Pure pricing engine. No DB calls, no side effects: data in, a priced result and its
explanation out. Every screen that shows a money or margin number calls this — the preview
endpoint, the save path, and (from Phase 3 on) the risk engine — so a number can never
diverge between what the rep sees while typing and what gets persisted.
"""

import uuid
from dataclasses import dataclass, field
from decimal import ROUND_HALF_UP, Decimal


def _round(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


@dataclass
class LineInput:
    product_id: uuid.UUID
    category_id: uuid.UUID
    line_type: str  # "ONE_TIME" | "RECURRING"
    qty: int
    unit_price: Decimal
    unit_cost: Decimal
    tax_pct: Decimal
    discount_pct: Decimal
    variant_id: uuid.UUID | None = None
    subscription_plan_id: uuid.UUID | None = None
    product_name: str = ""


@dataclass
class LinePricing:
    product_id: uuid.UUID
    product_name: str
    variant_id: uuid.UUID | None
    line_type: str
    qty: int
    unit_price: Decimal
    gross: Decimal
    discount_pct: Decimal
    discount_amount: Decimal
    net: Decimal
    tax_amount: Decimal
    unit_cost: Decimal
    cost_total: Decimal
    margin_amount: Decimal
    margin_pct: Decimal
    category_id: uuid.UUID
    ceiling_pct: Decimal
    overage_pct: Decimal
    weight: Decimal = Decimal("0")


@dataclass
class QuotationPricing:
    lines: list[LinePricing]
    subtotal: Decimal
    discount_total: Decimal
    tax_total: Decimal
    net_total: Decimal
    grand_total: Decimal
    margin_amount: Decimal
    margin_pct: Decimal
    explanations: list[str] = field(default_factory=list)


def price_quotation(
    lines: list[LineInput],
    ceilings: dict[uuid.UUID, Decimal],
) -> QuotationPricing:
    """`ceilings` maps category_id -> the ceiling already resolved for this customer's tier
    (matrix override -> category default -> tier base — see engine/ceilings.resolve_ceiling)."""

    priced: list[LinePricing] = []
    explanations: list[str] = []

    for line in lines:
        gross = _round(line.unit_price * line.qty)
        discount_amount = _round(gross * line.discount_pct / Decimal("100"))
        net = gross - discount_amount
        tax_amount = _round(net * line.tax_pct / Decimal("100"))
        cost_total = _round(line.unit_cost * line.qty)
        margin_amount = net - cost_total
        margin_pct = _round(margin_amount / net * Decimal("100")) if net > 0 else Decimal("0")

        ceiling_pct = ceilings.get(line.category_id, Decimal("0"))
        overage_pct = max(Decimal("0"), line.discount_pct - ceiling_pct)

        priced.append(
            LinePricing(
                product_id=line.product_id,
                product_name=line.product_name,
                variant_id=line.variant_id,
                line_type=line.line_type,
                qty=line.qty,
                unit_price=line.unit_price,
                gross=gross,
                discount_pct=line.discount_pct,
                discount_amount=discount_amount,
                net=net,
                tax_amount=tax_amount,
                unit_cost=line.unit_cost,
                cost_total=cost_total,
                margin_amount=margin_amount,
                margin_pct=margin_pct,
                category_id=line.category_id,
                ceiling_pct=ceiling_pct,
                overage_pct=overage_pct,
            )
        )

        if overage_pct > 0:
            explanations.append(
                f"{line.product_name}: {line.discount_pct}% discount is {overage_pct}pt over the "
                f"{ceiling_pct}% ceiling for this category."
            )
        else:
            explanations.append(
                f"{line.product_name}: {line.discount_pct}% discount is within the {ceiling_pct}% ceiling."
            )

    net_total = sum((p.net for p in priced), Decimal("0"))
    for p in priced:
        p.weight = _round(p.net / net_total) if net_total > 0 else Decimal("0")

    subtotal = sum((p.gross for p in priced), Decimal("0"))
    discount_total = sum((p.discount_amount for p in priced), Decimal("0"))
    tax_total = sum((p.tax_amount for p in priced), Decimal("0"))
    grand_total = net_total + tax_total
    margin_amount_total = sum((p.margin_amount for p in priced), Decimal("0"))
    margin_pct_total = _round(margin_amount_total / net_total * Decimal("100")) if net_total > 0 else Decimal("0")

    return QuotationPricing(
        lines=priced,
        subtotal=subtotal,
        discount_total=discount_total,
        tax_total=tax_total,
        net_total=net_total,
        grand_total=grand_total,
        margin_amount=margin_amount_total,
        margin_pct=margin_pct_total,
        explanations=explanations,
    )
