from __future__ import annotations

import time
from abc import ABC, abstractmethod
from typing import Any, Optional

from .models import ScrapeResult, Task
from .metrics import MetricsCollector


class BaseScraper(ABC):
    """Abstract base class defining the common scraping pipeline.

    Subclasses must implement fetch() and parse() to handle
    website-specific request and response logic.  The run() method
    orchestrates validation, fetching, parsing, and metrics recording.
    """

    def __init__(self, metrics: Optional[MetricsCollector] = None) -> None:
        self._metrics = metrics

    def run(self, task: Task) -> ScrapeResult:
        """Execute the full scraping pipeline for a single task.

        Returns a ScrapeResult regardless of success or failure,
        recording metrics and capturing any exceptions.
        """
        start_ms = self._now_ms()
        try:
            self.validate(task)
            response = self.fetch(task)
            data = self.parse(response)
            latency_ms = self._now_ms() - start_ms
            status_code = getattr(response, "status_code", None)
            success = status_code in (200, 201)
            result = ScrapeResult(
                task_id=task.task_id,
                source_id=task.source_id,
                url=task.url,
                success=success,
                status_code=status_code,
                latency_ms=latency_ms,
                data=data,
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
                status_code=None,
                latency_ms=latency_ms,
                data=None,
                error_type=type(exc).__name__,
            )
            if self._metrics:
                self._metrics.record_result(result)
            return result

    def validate(self, task: Task) -> None:
        """Validate task fields before fetching. Raises ValueError on invalid input."""
        if not task.url:
            raise ValueError("task.url is required")

    @abstractmethod
    def fetch(self, task: Task) -> Any:
        """Send an HTTP request for the given task and return the raw response."""

    @abstractmethod
    def parse(self, response: Any) -> Any:
        """Extract structured data from the raw HTTP response."""

    @staticmethod
    def _now_ms() -> int:
        """Return the current time in milliseconds since epoch."""
        return int(time.time() * 1000)