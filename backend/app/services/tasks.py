"""Background task execution.

The MVP runs jobs on a small in-process thread pool. That is deliberate: it
needs no broker, survives a laptop restart cycle, and keeps the deployment to
two processes. It is also the *only* place that knows how jobs are dispatched,
so replacing it with Celery/RQ/arq later means implementing ``submit`` against
a broker and changing nothing else in the codebase.
"""

from __future__ import annotations

import atexit
import logging
import threading
from collections.abc import Callable
from concurrent.futures import Future, ThreadPoolExecutor
from typing import Any

from app.config import settings

logger = logging.getLogger(__name__)


class TaskQueue:
    """Minimal fire-and-forget queue with visibility into depth."""

    def __init__(self, concurrency: int | None = None) -> None:
        self._concurrency = concurrency or settings.worker_concurrency
        self._executor: ThreadPoolExecutor | None = None
        self._lock = threading.Lock()
        self._pending = 0

    def _pool(self) -> ThreadPoolExecutor:
        if self._executor is None:
            with self._lock:
                if self._executor is None:
                    self._executor = ThreadPoolExecutor(
                        max_workers=self._concurrency, thread_name_prefix="allbee-worker"
                    )
        return self._executor

    def submit(self, fn: Callable[..., Any], *args: Any, **kwargs: Any) -> Future:
        with self._lock:
            self._pending += 1

        def _run() -> Any:
            try:
                return fn(*args, **kwargs)
            except Exception:  # noqa: BLE001 - a failed job must not kill the worker
                logger.exception("Background task %s failed", getattr(fn, "__name__", fn))
                raise
            finally:
                with self._lock:
                    self._pending -= 1

        return self._pool().submit(_run)

    @property
    def pending(self) -> int:
        return self._pending

    def shutdown(self, wait: bool = True) -> None:
        if self._executor is not None:
            self._executor.shutdown(wait=wait)
            self._executor = None


task_queue = TaskQueue()
atexit.register(lambda: task_queue.shutdown(wait=False))
