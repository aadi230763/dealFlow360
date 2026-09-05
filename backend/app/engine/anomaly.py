"""Pure anomaly detection. No DB calls, no side effects: plain samples in (already queried
by the API layer), flagged results out. Everything here is a read over data the rest of the
system already produces -- order-level discount %, last_activity_at, backorder allocations --
so nothing here is a new source of truth, only a new lens on existing ones.
"""

import statistics
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal

MIN_SAMPLE_SIZE = 5
FIXED_DELTA_PCT = Decimal("10")


# ---------------------------------------------------------------------------
# Stalled deals
# ---------------------------------------------------------------------------


@dataclass
class QuotationActivitySample:
    quotation_id: uuid.UUID
    number: str
    customer_name: str
    owner_name: str
    grand_total: Decimal
    last_activity_at: datetime


@dataclass
class StalledDeal:
    quotation_id: uuid.UUID
    number: str
    customer_name: str
    owner_name: str
    idle_days: int
    value_at_risk: Decimal
    flagged_at: datetime


def find_stalled_deals(
    samples: list[QuotationActivitySample], threshold_days: int, now: datetime
) -> list[StalledDeal]:
    """Samples must already be filtered to non-terminal statuses by the caller."""
    flagged: list[StalledDeal] = []
    for s in samples:
        idle_days = (now - s.last_activity_at).days
        if idle_days > threshold_days:
            flagged.append(
                StalledDeal(
                    quotation_id=s.quotation_id,
                    number=s.number,
                    customer_name=s.customer_name,
                    owner_name=s.owner_name,
                    idle_days=idle_days,
                    value_at_risk=s.grand_total,
                    flagged_at=s.last_activity_at,
                )
            )
    return sorted(flagged, key=lambda d: d.value_at_risk, reverse=True)


# ---------------------------------------------------------------------------
# Discount anomalies
# ---------------------------------------------------------------------------


@dataclass
class QuotationDiscountSample:
    quotation_id: uuid.UUID
    number: str
    customer_name: str
    rep_id: uuid.UUID
    rep_name: str
    discount_pct: Decimal  # order-level: discount_total / subtotal * 100
    created_at: datetime


@dataclass
class DiscountAnomaly:
    quotation_id: uuid.UUID
    number: str
    customer_name: str
    rep_id: uuid.UUID
    rep_name: str
    discount_pct: Decimal
    baseline_pct: Decimal
    z_score: Decimal | None
    method: str  # "zscore" | "fixed_delta"
    flagged_at: datetime


def find_discount_anomalies(
    samples: list[QuotationDiscountSample], z_threshold: Decimal
) -> list[DiscountAnomaly]:
    """z-score against the rep's own baseline (rolling mean/stddev of their own order-level
    discount %). A rep with fewer than MIN_SAMPLE_SIZE quotes doesn't have a reliable
    baseline yet, so falls back to a fixed-delta rule against the org-wide average instead."""
    by_rep: dict[uuid.UUID, list[QuotationDiscountSample]] = {}
    for s in samples:
        by_rep.setdefault(s.rep_id, []).append(s)

    overall_avg = (
        statistics.fmean(float(s.discount_pct) for s in samples) if samples else 0.0
    )

    flagged: list[DiscountAnomaly] = []
    for rep_samples in by_rep.values():
        discounts = [float(s.discount_pct) for s in rep_samples]
        if len(discounts) < MIN_SAMPLE_SIZE:
            baseline = Decimal(str(round(overall_avg, 2)))
            for s in rep_samples:
                if s.discount_pct - baseline > FIXED_DELTA_PCT:
                    flagged.append(
                        DiscountAnomaly(
                            quotation_id=s.quotation_id,
                            number=s.number,
                            customer_name=s.customer_name,
                            rep_id=s.rep_id,
                            rep_name=s.rep_name,
                            discount_pct=s.discount_pct,
                            baseline_pct=baseline,
                            z_score=None,
                            method="fixed_delta",
                            flagged_at=s.created_at,
                        )
                    )
            continue

        mean = statistics.fmean(discounts)
        stdev = statistics.pstdev(discounts, mu=mean)
        if stdev == 0:
            continue
        baseline = Decimal(str(round(mean, 2)))
        for s in rep_samples:
            z = (float(s.discount_pct) - mean) / stdev
            if z > float(z_threshold):
                flagged.append(
                    DiscountAnomaly(
                        quotation_id=s.quotation_id,
                        number=s.number,
                        customer_name=s.customer_name,
                        rep_id=s.rep_id,
                        rep_name=s.rep_name,
                        discount_pct=s.discount_pct,
                        baseline_pct=baseline,
                        z_score=Decimal(str(round(z, 2))),
                        method="zscore",
                        flagged_at=s.created_at,
                    )
                )
    return sorted(flagged, key=lambda a: (a.z_score or Decimal("999")), reverse=True)


# ---------------------------------------------------------------------------
# Delivery slippage
# ---------------------------------------------------------------------------


@dataclass
class FulfillmentBackorderSample:
    fulfillment_id: uuid.UUID
    quotation_id: uuid.UUID
    number: str
    customer_name: str
    created_at: datetime
    backorder_qty: int


@dataclass
class DeliverySlippage:
    fulfillment_id: uuid.UUID
    quotation_id: uuid.UUID
    number: str
    customer_name: str
    days_late: int
    backorder_qty: int
    flagged_at: datetime


def find_delivery_slippage(
    samples: list[FulfillmentBackorderSample], promise_days: int, now: datetime
) -> list[DeliverySlippage]:
    """`samples` must already be filtered to fulfillments with at least one open backorder
    allocation. The promise date is derived (created_at + promise_days), not stored -- no new
    column, consistent with the rest of this module reading only existing data."""
    flagged: list[DeliverySlippage] = []
    for s in samples:
        promised_at = s.created_at + timedelta(days=promise_days)
        if now > promised_at:
            flagged.append(
                DeliverySlippage(
                    fulfillment_id=s.fulfillment_id,
                    quotation_id=s.quotation_id,
                    number=s.number,
                    customer_name=s.customer_name,
                    days_late=(now - promised_at).days,
                    backorder_qty=s.backorder_qty,
                    flagged_at=promised_at,
                )
            )
    return sorted(flagged, key=lambda d: d.days_late, reverse=True)
