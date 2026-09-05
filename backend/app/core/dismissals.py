"""In-memory, per-quotation dismissed-suggestion set. Explicitly "for the session"
per the spec -- not persisted, cleared on server restart. Single-process dev server,
same tradeoff as core/events.py's SSE broadcaster."""

import uuid

_dismissed: dict[uuid.UUID, set[uuid.UUID]] = {}


def dismiss(quotation_id: uuid.UUID, product_id: uuid.UUID) -> None:
    _dismissed.setdefault(quotation_id, set()).add(product_id)


def get_dismissed(quotation_id: uuid.UUID) -> set[uuid.UUID]:
    return _dismissed.get(quotation_id, set())
