from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Optional

from .models import ScrapeResult, Task
from .metrics import MetricsCollector


class BaseScraper(ABC):
    def __init__(self, metrics: Optional[MetricsCollector] = None) -> None:
        self._metrics = metrics

    def run(self, task: Task) -> ScrapeResult:
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
        if not task.url:
            raise ValueError("task.url is required")

    @abstractmethod
    def fetch(self, task: Task) -> Any:
        raise NotImplementedError

    @abstractmethod
    def parse(self, response: Any) -> Any:
        raise NotImplementedError

    @staticmethod
    def _now_ms() -> int:
        import time

        return int(time.time() * 1000)
