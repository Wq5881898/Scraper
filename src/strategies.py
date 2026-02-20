from __future__ import annotations

from abc import ABC, abstractmethod

from .controller import ThreadPoolController
from .models import MetricsSnapshot


class ControlStrategy(ABC):
    @abstractmethod
    def should_apply(self, snapshot: MetricsSnapshot) -> bool:
        raise NotImplementedError

    @abstractmethod
    def apply(self, controller: ThreadPoolController, snapshot: MetricsSnapshot) -> None:
        raise NotImplementedError


class ReduceConcurrencyStrategy(ControlStrategy):
    def __init__(self, threshold_429: float = 0.05, threshold_timeout: float = 0.10, min_limit: int = 1) -> None:
        self._threshold_429 = threshold_429
        self._threshold_timeout = threshold_timeout
        self._min_limit = min_limit

    def should_apply(self, snapshot: MetricsSnapshot) -> bool:
        if snapshot.total_requests == 0:
            return False
        rate_429 = snapshot.http_429_count / snapshot.total_requests
        rate_timeout = snapshot.timeout_count / snapshot.total_requests
        return rate_429 >= self._threshold_429 or rate_timeout >= self._threshold_timeout

    def apply(self, controller: ThreadPoolController, snapshot: MetricsSnapshot) -> None:
        controller.set_concurrency_limit(max(self._min_limit, controller.limit - 1))


class IncreaseConcurrencyStrategy(ControlStrategy):
    def __init__(self, threshold_timeout: float = 0.02, max_limit: int = 20) -> None:
        self._threshold_timeout = threshold_timeout
        self._max_limit = max_limit

    def should_apply(self, snapshot: MetricsSnapshot) -> bool:
        if snapshot.total_requests == 0:
            return False
        rate_timeout = snapshot.timeout_count / snapshot.total_requests
        return rate_timeout < self._threshold_timeout

    def apply(self, controller: ThreadPoolController, snapshot: MetricsSnapshot) -> None:
        controller.set_concurrency_limit(min(self._max_limit, controller.limit + 1))


class ChangeProxyStrategy(ControlStrategy):
    def __init__(self) -> None:
        self._last_applied = 0

    def should_apply(self, snapshot: MetricsSnapshot) -> bool:
        return snapshot.ip_ban_suspected_count > 0

    def apply(self, controller: ThreadPoolController, snapshot: MetricsSnapshot) -> None:
        self._last_applied += 1
