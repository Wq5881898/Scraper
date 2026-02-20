"""Tests for the adaptive control strategy classes."""

import unittest

from src.controller import ThreadPoolController
from src.models import MetricsSnapshot
from src.strategies import (
    ReduceConcurrencyStrategy,
    IncreaseConcurrencyStrategy,
    ChangeProxyStrategy,
)


def _make_snapshot(**overrides) -> MetricsSnapshot:
    """Helper to build a MetricsSnapshot with sensible defaults."""
    defaults = dict(
        window_secs=30,
        total_requests=100,
        success_count=90,
        timeout_count=0,
        conn_error_count=0,
        http_429_count=0,
        http_403_count=0,
        ip_ban_suspected_count=0,
        avg_latency_ms=100.0,
        timestamp=1000000.0,
    )
    defaults.update(overrides)
    return MetricsSnapshot(**defaults)


class TestReduceConcurrencyStrategy(unittest.TestCase):
    """Verify ReduceConcurrencyStrategy activates and reduces limit."""

    def test_should_apply_when_429_rate_high(self):
        """Should activate when HTTP 429 rate exceeds threshold."""
        strategy = ReduceConcurrencyStrategy(threshold_429=0.05)
        snapshot = _make_snapshot(http_429_count=10, total_requests=100)
        self.assertTrue(strategy.should_apply(snapshot))

    def test_should_not_apply_when_rates_low(self):
        """Should not activate when all error rates are below thresholds."""
        strategy = ReduceConcurrencyStrategy(threshold_429=0.05, threshold_timeout=0.10)
        snapshot = _make_snapshot(http_429_count=1, timeout_count=1, total_requests=100)
        self.assertFalse(strategy.should_apply(snapshot))

    def test_apply_reduces_limit(self):
        """Applying should decrease the concurrency limit by one."""
        controller = ThreadPoolController(max_workers=8, initial_limit=5)
        strategy = ReduceConcurrencyStrategy()
        snapshot = _make_snapshot()
        strategy.apply(controller, snapshot)
        self.assertEqual(controller.limit, 4)

    def test_does_not_go_below_minimum(self):
        """Limit should not drop below min_limit."""
        controller = ThreadPoolController(max_workers=8, initial_limit=1)
        strategy = ReduceConcurrencyStrategy(min_limit=1)
        snapshot = _make_snapshot()
        strategy.apply(controller, snapshot)
        self.assertEqual(controller.limit, 1)

    def test_should_not_apply_when_no_requests(self):
        """Should not activate when there are zero requests in the window."""
        strategy = ReduceConcurrencyStrategy()
        snapshot = _make_snapshot(total_requests=0)
        self.assertFalse(strategy.should_apply(snapshot))


class TestIncreaseConcurrencyStrategy(unittest.TestCase):
    """Verify IncreaseConcurrencyStrategy activates and increases limit."""

    def test_should_apply_when_stable(self):
        """Should activate when timeout rate is below threshold."""
        strategy = IncreaseConcurrencyStrategy(threshold_timeout=0.02)
        snapshot = _make_snapshot(timeout_count=0, total_requests=100)
        self.assertTrue(strategy.should_apply(snapshot))

    def test_should_not_apply_when_timeouts_high(self):
        """Should not activate when timeout rate exceeds threshold."""
        strategy = IncreaseConcurrencyStrategy(threshold_timeout=0.02)
        snapshot = _make_snapshot(timeout_count=5, total_requests=100)
        self.assertFalse(strategy.should_apply(snapshot))

    def test_apply_increases_limit(self):
        """Applying should increase the concurrency limit by one."""
        controller = ThreadPoolController(max_workers=8, initial_limit=3)
        strategy = IncreaseConcurrencyStrategy()
        snapshot = _make_snapshot()
        strategy.apply(controller, snapshot)
        self.assertEqual(controller.limit, 4)

    def test_does_not_exceed_maximum(self):
        """Limit should not exceed max_limit."""
        controller = ThreadPoolController(max_workers=25, initial_limit=20)
        strategy = IncreaseConcurrencyStrategy(max_limit=20)
        snapshot = _make_snapshot()
        strategy.apply(controller, snapshot)
        self.assertEqual(controller.limit, 20)


class TestChangeProxyStrategy(unittest.TestCase):
    """Verify ChangeProxyStrategy activates on suspected IP bans."""

    def test_should_apply_when_ip_ban_suspected(self):
        """Should activate when IP ban is suspected."""
        strategy = ChangeProxyStrategy()
        snapshot = _make_snapshot(ip_ban_suspected_count=1)
        self.assertTrue(strategy.should_apply(snapshot))

    def test_should_not_apply_when_no_ban(self):
        """Should not activate when no IP ban is suspected."""
        strategy = ChangeProxyStrategy()
        snapshot = _make_snapshot(ip_ban_suspected_count=0)
        self.assertFalse(strategy.should_apply(snapshot))

    def test_apply_increments_counter(self):
        """Applying should increment the internal counter (placeholder behaviour)."""
        controller = ThreadPoolController(max_workers=8, initial_limit=3)
        strategy = ChangeProxyStrategy()
        snapshot = _make_snapshot()
        strategy.apply(controller, snapshot)
        self.assertEqual(strategy._last_applied, 1)


if __name__ == "__main__":
    unittest.main()
