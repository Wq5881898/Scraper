"""Tests for the MetricsCollector class."""

import time
import unittest

from src.metrics import MetricsCollector
from src.models import ScrapeResult


def _make_result(**overrides) -> ScrapeResult:
    """Helper to build a ScrapeResult with sensible defaults."""
    defaults = dict(
        task_id="t1",
        source_id="web1",
        url="https://example.com",
        success=True,
        status_code=200,
        latency_ms=100,
        data=None,
        error_type=None,
    )
    defaults.update(overrides)
    return ScrapeResult(**defaults)


class TestMetricsCollector(unittest.TestCase):
    """Verify metrics recording and snapshot aggregation."""

    def test_empty_snapshot(self):
        """Snapshot with no events should have all zeros."""
        metrics = MetricsCollector()
        snap = metrics.snapshot(window_secs=30)
        self.assertEqual(snap.total_requests, 0)
        self.assertEqual(snap.success_count, 0)
        self.assertEqual(snap.avg_latency_ms, 0.0)

    def test_records_success(self):
        """Successful results should be counted correctly."""
        metrics = MetricsCollector()
        metrics.record_result(_make_result(success=True, status_code=200))
        metrics.record_result(_make_result(success=True, status_code=200))
        snap = metrics.snapshot(window_secs=30)
        self.assertEqual(snap.total_requests, 2)
        self.assertEqual(snap.success_count, 2)

    def test_records_errors(self):
        """Error results should be categorized correctly."""
        metrics = MetricsCollector()
        metrics.record_result(_make_result(success=False, status_code=429, error_type="HTTP_429"))
        metrics.record_result(_make_result(success=False, status_code=None, error_type="Timeout"))
        metrics.record_result(_make_result(success=False, status_code=None, error_type="ConnectionError"))
        snap = metrics.snapshot(window_secs=30)
        self.assertEqual(snap.total_requests, 3)
        self.assertEqual(snap.http_429_count, 1)
        self.assertEqual(snap.timeout_count, 1)
        self.assertEqual(snap.conn_error_count, 1)

    def test_ip_ban_detection(self):
        """Three or more HTTP 403 responses should flag an IP ban suspicion."""
        metrics = MetricsCollector()
        for _ in range(3):
            metrics.record_result(_make_result(success=False, status_code=403, error_type="HTTP_403"))
        snap = metrics.snapshot(window_secs=30)
        self.assertEqual(snap.ip_ban_suspected_count, 1)

    def test_no_ip_ban_below_threshold(self):
        """Fewer than 3 HTTP 403 responses should not flag an IP ban."""
        metrics = MetricsCollector()
        for _ in range(2):
            metrics.record_result(_make_result(success=False, status_code=403, error_type="HTTP_403"))
        snap = metrics.snapshot(window_secs=30)
        self.assertEqual(snap.ip_ban_suspected_count, 0)

    def test_average_latency(self):
        """Average latency should be computed correctly."""
        metrics = MetricsCollector()
        metrics.record_result(_make_result(latency_ms=100))
        metrics.record_result(_make_result(latency_ms=200))
        snap = metrics.snapshot(window_secs=30)
        self.assertAlmostEqual(snap.avg_latency_ms, 150.0)

    def test_export_json(self):
        """export_json should return all recorded events as dicts."""
        metrics = MetricsCollector()
        metrics.record_result(_make_result())
        exported = metrics.export_json()
        self.assertEqual(len(exported), 1)
        self.assertIn("task_id", exported[0])


if __name__ == "__main__":
    unittest.main()
