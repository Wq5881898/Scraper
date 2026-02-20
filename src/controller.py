from __future__ import annotations

import threading
from concurrent.futures import Future, ThreadPoolExecutor
from typing import Callable

from .models import ScrapeResult, Task


class ThreadPoolController:
    """Manages concurrent task execution using a bounded thread pool.

    Refactor goal:
    - Fix potential deadlock/blocking in set_concurrency_limit() when decreasing.
    - Do NOT change scraper behaviour; only scheduling behaviour.
    """

    def __init__(self, max_workers: int, initial_limit: int) -> None:
        self._executor = ThreadPoolExecutor(max_workers=max_workers)

        self._lock = threading.Lock()
        self._cv = threading.Condition(self._lock)

        self._limit = max(1, initial_limit)
        self._active = 0
        self._running = False

    def start(self) -> None:
        self._running = True

    def stop(self, wait: bool = True) -> None:
        with self._cv:
            self._running = False
            self._cv.notify_all()
        self._executor.shutdown(wait=wait, cancel_futures=False)

    def submit(self, fn: Callable[[Task], ScrapeResult], task: Task) -> Future:
        """Submit a scraping function for execution, blocking if at concurrency limit."""
        with self._cv:
            while self._running and self._active >= self._limit:
                self._cv.wait(timeout=0.5)

            if not self._running:
                return self._executor.submit(self._stopped_result, task)

            self._active += 1

        return self._executor.submit(self._wrap_task, fn, task)

    def _wrap_task(self, fn: Callable[[Task], ScrapeResult], task: Task) -> ScrapeResult:
        try:
            return fn(task)
        finally:
            with self._cv:
                self._active = max(0, self._active - 1)
                self._cv.notify_all()

    @staticmethod
    def _stopped_result(task: Task) -> ScrapeResult:
        return ScrapeResult(
            task_id=task.task_id,
            source_id=task.source_id,
            url=task.url,
            success=False,
            status_code=None,
            latency_ms=0,
            data=None,
            error_type="ControllerStopped",
        )

    def set_concurrency_limit(self, new_limit: int) -> tuple[int, int]:
        """Dynamically adjust the concurrency limit at runtime (non-blocking)."""
        with self._cv:
            old_limit = self._limit
            self._limit = max(1, int(new_limit))
            self._cv.notify_all()
            return old_limit, self._limit

    @property
    def limit(self) -> int:
        return self._limit