"""In-process pub/sub that powers the live gallery.

Photos are processed on worker *threads* but delivered to browsers from the
*asyncio* loop, so every publish is marshalled back onto the loop with
``call_soon_threadsafe``. Subscribers get a bounded queue: a guest on a slow
phone gets the newest events and drops the backlog rather than growing memory
on the server.

Scaling past one API process means replacing the internals here with Redis
pub/sub; the ``publish`` / ``subscribe`` contract stays the same.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
from collections import defaultdict
from typing import Any

logger = logging.getLogger(__name__)

QUEUE_MAXSIZE = 64


class LiveBus:
    def __init__(self) -> None:
        self._subscribers: dict[str, set[asyncio.Queue]] = defaultdict(set)
        self._loop: asyncio.AbstractEventLoop | None = None

    def bind_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        """Called once on startup so worker threads know where to deliver."""
        self._loop = loop

    # -- publishing --------------------------------------------------------
    def publish(self, channel: str, event: str, data: dict[str, Any]) -> None:
        """Safe to call from any thread."""
        if not self._subscribers.get(channel):
            return
        payload = {"event": event, "data": data}
        loop = self._loop
        if loop is None or loop.is_closed():
            return
        try:
            loop.call_soon_threadsafe(self._deliver, channel, payload)
        except RuntimeError:  # pragma: no cover - loop shutting down
            pass

    def _deliver(self, channel: str, payload: dict[str, Any]) -> None:
        for queue in list(self._subscribers.get(channel, ())):
            try:
                queue.put_nowait(payload)
            except asyncio.QueueFull:
                # Drop the oldest so the client still receives current state.
                with contextlib.suppress(asyncio.QueueEmpty):
                    queue.get_nowait()
                with contextlib.suppress(asyncio.QueueFull):
                    queue.put_nowait(payload)

    # -- subscribing -------------------------------------------------------
    @contextlib.contextmanager
    def subscribe(self, channel: str):
        queue: asyncio.Queue = asyncio.Queue(maxsize=QUEUE_MAXSIZE)
        self._subscribers[channel].add(queue)
        try:
            yield queue
        finally:
            self._subscribers[channel].discard(queue)
            if not self._subscribers[channel]:
                self._subscribers.pop(channel, None)

    def subscriber_count(self, channel: str) -> int:
        return len(self._subscribers.get(channel, ()))


live_bus = LiveBus()


def sse_format(event: str, data: dict[str, Any]) -> str:
    """Serialise one Server-Sent Event frame."""
    return f"event: {event}\ndata: {json.dumps(data, default=str)}\n\n"
