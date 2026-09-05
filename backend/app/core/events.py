"""Minimal in-process SSE broadcaster. Single-process dev server is fine for a 24h build --
route handlers run in FastAPI's threadpool, so publish() hops back onto the event loop
via call_soon_threadsafe rather than touching the asyncio.Queue directly from a worker thread."""

import asyncio
from typing import Any

_subscribers: set[asyncio.Queue] = set()
_loop: asyncio.AbstractEventLoop | None = None


def set_loop(loop: asyncio.AbstractEventLoop) -> None:
    global _loop
    _loop = loop


async def subscribe():
    queue: asyncio.Queue = asyncio.Queue()
    _subscribers.add(queue)
    try:
        while True:
            yield await queue.get()
    finally:
        _subscribers.discard(queue)


def publish(event: dict[str, Any]) -> None:
    if _loop is None:
        return
    for queue in list(_subscribers):
        _loop.call_soon_threadsafe(queue.put_nowait, event)
