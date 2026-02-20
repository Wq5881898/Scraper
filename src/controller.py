from __future__ import annotations

import threading
from concurrent.futures import Future, ThreadPoolExecutor
from typing import Callable, Iterable, Optional

from .models import ScrapeResult, Task


class ThreadPoolController:
    """Manages concurrent task execution using a bounded thread pool.

    Provides a semaphore-based concurrency limiter that can be
    adjusted at runtime by the SmartController."""

    def __init__(self, max_workers: int, initial_limit: int) -> None:
        self._executor = ThreadPoolExecutor(max_workers=max_workers)
        self._limit_lock = threading.Lock()
        self._limit = max(1, initial_limit)
        self._semaphore = threading.Semaphore(self._limit)
        self._running = False

    def start(self) -> None:
        """Mark the controller as running and ready to accept tasks."""
        self._running = True

    def stop(self, wait: bool = True) -> None:
        """Shut down the thread pool and stop accepting new tasks."""
        self._running = False
        self._executor.shutdown(wait=wait, cancel_futures=False)

    def submit(self, fn: Callable[[Task], ScrapeResult], task: Task) -> Future:
        """Submit a scraping function for execution, blocking if at concurrency limit."""
        self._semaphore.acquire()
        future = self._executor.submit(self._wrap_task, fn, task)
        return future

    def _wrap_task(self, fn: Callable[[Task], ScrapeResult], task: Task) -> ScrapeResult:
        """Execute the task and release the semaphore when done."""
        try:
            return fn(task)
        finally:
            self._semaphore.release()

    def set_concurrency_limit(self, new_limit: int) -> tuple[int, int]:
        """Dynamically adjust the concurrency limit at runtime.

        Returns a tuple of (old_limit, new_limit)."""
        with self._limit_lock:
            old_limit = self._limit
            new_limit = max(1, new_limit)
            delta = new_limit - self._limit
            if delta > 0:
                for _ in range(delta):
                    self._semaphore.release()
            elif delta < 0:
                for _ in range(-delta):
                    self._semaphore.acquire()
            self._limit = new_limit
            return old_limit, new_limit

    @property
    def limit(self) -> int:
        """Return the current concurrency limit."""
        return self._limit
