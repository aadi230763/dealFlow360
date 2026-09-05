"""Pure billing engine. No DB calls, no side effects: a start date and a rate in, period
dates and amounts out. Two things live here: turning a subscription plan's interval into
real calendar dates, and the proration math for mid-cycle quantity changes and cancellations.
"""

import calendar
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal

from app.models.subscription_plan import Interval, ProrationPolicy

_MONTHS_PER_INTERVAL = {
    Interval.MONTHLY: 1,
    Interval.QUARTERLY: 3,
    Interval.YEARLY: 12,
}


def _round(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _shift_months(start: date, total_months: int) -> date:
    month_index = start.month - 1 + total_months
    year = start.year + month_index // 12
    month = month_index % 12 + 1
    day = min(start.day, calendar.monthrange(year, month)[1])
    return date(year, month, day)


def add_period(start: date, interval: Interval, interval_count: int) -> date:
    """Adds `interval_count` periods of `interval` to `start`, using real calendar-month
    arithmetic (so Jan 31 + 1 month lands on Feb 28/29, not a fixed day count)."""
    return _shift_months(start, _MONTHS_PER_INTERVAL[interval] * interval_count)


def subtract_period(end: date, interval: Interval, interval_count: int) -> date:
    """Inverse of add_period -- used to recover a period's start from its end (the schedule
    only persists next_billing_date, so the current period's start is derived on demand)."""
    return _shift_months(end, -_MONTHS_PER_INTERVAL[interval] * interval_count)


@dataclass
class PeriodOccurrence:
    period_start: date
    period_end: date
    amount: Decimal


@dataclass
class ScheduleBuild:
    first_period: PeriodOccurrence
    next_billing_date: date
    upcoming: list[PeriodOccurrence]


def build_schedule(
    start_date: date, interval: Interval, interval_count: int, amount: Decimal, occurrences: int = 12
) -> ScheduleBuild:
    periods: list[PeriodOccurrence] = []
    cursor = start_date
    for _ in range(occurrences):
        period_end = add_period(cursor, interval, interval_count)
        periods.append(PeriodOccurrence(period_start=cursor, period_end=period_end, amount=amount))
        cursor = period_end
    return ScheduleBuild(first_period=periods[0], next_billing_date=periods[0].period_end, upcoming=periods)


def invoice_amount_for_qty(
    line_net: Decimal, line_tax: Decimal, line_qty: int, shipped_qty: int
) -> tuple[Decimal, Decimal]:
    """Proportional amount/tax for a partial shipment of a one-time line."""
    if line_qty <= 0:
        return Decimal("0"), Decimal("0")
    fraction = Decimal(shipped_qty) / Decimal(line_qty)
    return _round(line_net * fraction), _round(line_tax * fraction)


@dataclass
class ProrationResult:
    delta_amount: Decimal  # always >= 0; is_credit says which direction
    is_credit: bool
    days_remaining: int
    days_in_period: int
    new_period_amount: Decimal  # the new full-period rate, for display


def prorate(
    unit_rate_per_period: Decimal,
    old_qty: int,
    new_qty: int,
    change_date: date,
    period_start: date,
    period_end: date,
    policy: ProrationPolicy,
) -> ProrationResult:
    days_in_period = max(1, (period_end - period_start).days)
    days_remaining = max(0, (period_end - change_date).days)
    delta_qty = new_qty - old_qty
    full_delta = unit_rate_per_period * delta_qty
    new_period_amount = unit_rate_per_period * new_qty

    if policy == ProrationPolicy.NONE or delta_qty == 0:
        charge = Decimal("0")
    elif policy == ProrationPolicy.FULL_PERIOD:
        charge = full_delta
    else:  # DAILY_PRORATE
        charge = _round(full_delta * Decimal(days_remaining) / Decimal(days_in_period))

    return ProrationResult(
        delta_amount=abs(charge),
        is_credit=charge < 0,
        days_remaining=days_remaining,
        days_in_period=days_in_period,
        new_period_amount=_round(new_period_amount),
    )


def cancel_credit(
    unit_rate_per_period: Decimal,
    qty: int,
    change_date: date,
    period_start: date,
    period_end: date,
    policy: str,
) -> Decimal:
    if policy != "CREDIT_REMAINING":
        return Decimal("0")
    days_in_period = max(1, (period_end - period_start).days)
    days_remaining = max(0, (period_end - change_date).days)
    full_amount = unit_rate_per_period * qty
    return _round(full_amount * Decimal(days_remaining) / Decimal(days_in_period))
