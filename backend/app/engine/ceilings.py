from decimal import Decimal

"""Pure resolution helper: matrix override -> category default -> tier base.

Shared by the admin ceiling-matrix screen (Phase 1) and the risk engine (Phase 3),
so both read the exact same rule instead of duplicating the fallback chain.
"""


def resolve_ceiling(
    *,
    tier_base: Decimal,
    category_default: Decimal,
    override: Decimal | None,
) -> Decimal:
    if override is not None:
        return override
    if category_default is not None:
        return category_default
    return tier_base
