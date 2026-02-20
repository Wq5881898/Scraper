from __future__ import annotations

from abc import ABC, abstractmethod

from .controller import ThreadPoolController
from .models import MetricsSnapshot


class ControlStrategy(ABC):
    """Abstract base class for adaptive control strategies.

    Each strategy evaluates a MetricsSnapshot and decides whether
    to adjust system behaviour (e.g. concurrency, proxy rotation)."""

    @abstractmethod
    def should_apply(self, snapshot: MetricsSnapshot) -> bool:
        """Return True if this strategy should be activated given current metrics."""
        raise NotImplementedError

    @abstractmethod
    def apply(self, controller: ThreadPoolController, snapshot: MetricsSnapshot) -> None:
        """Execute the strategy's adjustment on the controller."""
        raise NotImplementedError


class ReduceConcurrencyStrategy(ControlStrategy):
    """Reduces thread pool concurrency when rate-limiting or timeouts are detected."""

    def __init__(self, threshold_429: float = 0.05, threshold_timeout: float = 0.10, min_limit: int = 1) -> None:
        self._threshold_429 = threshold_429
        self._threshold_timeout = threshold_timeout
        self._min_limit = min_limit

    def should_apply(self, snapshot: MetricsSnapshot) -> bool:
        """Activate when HTTP 429 or timeout rate exceeds configured thresholds."""
        if snapshot.total_requests == 0:
            return False
        rate_429 = snapshot.http_429_count / snapshot.total_requests
        rate_timeout = snapshot.timeout_count / snapshot.total_requests
        return rate_429 >= self._threshold_429 or rate_timeout >= self._threshold_timeout

    def apply(self, controller: ThreadPoolController, snapshot: MetricsSnapshot) -> None:
        """Decrease the concurrency limit by one, respecting the minimum."""
        controller.set_concurrency_limit(max(self._min_limit, controller.limit - 1))


class IncreaseConcurrencyStrategy(ControlStrategy):
    """Increases thread pool concurrency when error rates are low and stable."""

    def __init__(self, threshold_timeout: float = 0.02, max_limit: int = 20) -> None:
        self._threshold_timeout = threshold_timeout
        self._max_limit = max_limit

    def should_apply(self, snapshot: MetricsSnapshot) -> bool:
        """Activate when the timeout rate is below the safe threshold."""
        if snapshot.total_requests == 0:
            return False
        rate_timeout = snapshot.timeout_count / snapshot.total_requests
        return rate_timeout < self._threshold_timeout

    def apply(self, controller: ThreadPoolController, snapshot: MetricsSnapshot) -> None:
        """Increase the concurrency limit by one, respecting the maximum."""
        controller.set_concurrency_limit(min(self._max_limit, controller.limit + 1))


class ChangeProxyStrategy(ControlStrategy):
    """Placeholder strategy for proxy rotation when IP bans are suspected.

    Proxy rotation logic will be implemented in a future phase.
    Currently logs activation count for metrics tracking purposes."""

    def __init__(self) -> None:
        self._last_applied = 0

    def should_apply(self, snapshot: MetricsSnapshot) -> bool:
        """Activate when the system suspects an IP ban (multiple HTTP 403 responses)."""
        return snapshot.ip_ban_suspected_count > 0

    def apply(self, controller: ThreadPoolController, snapshot: MetricsSnapshot) -> None:
        """Record activation count. Actual proxy switching is planned for Phase 3."""
        self._last_applied += 1
