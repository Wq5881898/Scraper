from __future__ import annotations

import time
from abc import ABC, abstractmethod
from typing import Any, Optional

from .models import ScrapeResult, Task
from .metrics import MetricsCollector


class BaseScraper(ABC):
    """Abstract base class defining a common scraping pipeline.

    Improvements:
    - Treat any 2xx status as success (not only 200/201).
    - If HTTP error occurs, still keep parsed data when possible.
    - Includes error_type with HTTP code, or exception class.
    """

    def __init__(self, metrics: Optional[MetricsCollector] = None) -> None:
        self._metrics = metrics

    def run(self, task: Task) -> ScrapeResult:
        start_ms = self._now_ms()
        status_code = None

        try:
            self.validate(task)
            response = self.fetch(task)
            status_code = getattr(response, "status_code", None)

            parsed = None
            try:
                parsed = self.parse(response)
            except Exception as parse_exc:  # noqa: BLE001
                latency_ms = self._now_ms() - start_ms
                result = ScrapeResult(
                    task_id=task.task_id,
                    source_id=task.source_id,
                    url=task.url,
                    success=False,
                    status_code=status_code,
                    latency_ms=latency_ms,
                    data={"parse_error": type(parse_exc).__name__},
                    error_type=type(parse_exc).__name__,
                )
                if self._metrics:
                    self._metrics.record_result(result)
                return result

            latency_ms = self._now_ms() - start_ms
            success = bool(status_code is not None and 200 <= int(status_code) < 300)

            result = ScrapeResult(
                task_id=task.task_id,
                source_id=task.source_id,
                url=task.url,
                success=success,
                status_code=status_code,
                latency_ms=latency_ms,
                data=parsed,
                error_type=None if success else f"HTTP_{status_code}",
            )
            if self._metrics:
                self._metrics.record_result(result)
            return result

        except Exception as exc:  # noqa: BLE001
            latency_ms = self._now_ms() - start_ms
            result = ScrapeResult(
                task_id=task.task_id,
                source_id=task.source_id,
                url=task.url,
                success=False,
                status_code=status_code,
                latency_ms=latency_ms,
                data=None,
                error_type=type(exc).__name__,
            )
            if self._metrics:
                self._metrics.record_result(result)
            return result

    def validate(self, task: Task) -> None:
        if not task.url:
            raise ValueError("task.url is required")

    @abstractmethod
    def fetch(self, task: Task) -> Any:
        ...

    @abstractmethod
    def parse(self, response: Any) -> Any:
        ...

    @staticmethod
    def _now_ms() -> int:
        return int(time.time() * 1000)