"""Tests for data model classes."""

import unittest

from src.models import Task, ScrapeResult, MetricsSnapshot


class TestTask(unittest.TestCase):
    """Verify Task dataclass creation and immutability."""

    def test_create_task_with_defaults(self):
        """Task should be creatable with just required fields."""
        task = Task(task_id="t1", source_id="web1", url="https://example.com")
        self.assertEqual(task.task_id, "t1")
        self.assertEqual(task.params, {})
        self.assertEqual(task.meta, {})

    def test_task_is_immutable(self):
        """Frozen dataclass should raise on attribute assignment."""
        task = Task(task_id="t1", source_id="web1", url="https://example.com")
        with self.assertRaises(AttributeError):
            task.url = "https://other.com"

    def test_create_task_with_params_and_meta(self):
        """Task should store params and meta correctly."""
        task = Task(
            task_id="t2",
            source_id="web2",
            url="https://api.example.com",
            params={"q": "test"},
            meta={"chain": "bsc"},
        )
        self.assertEqual(task.params["q"], "test")
        self.assertEqual(task.meta["chain"], "bsc")


class TestScrapeResult(unittest.TestCase):
    """Verify ScrapeResult dataclass creation."""

    def test_successful_result(self):
        """A successful result should have success=True and no error_type."""
        result = ScrapeResult(
            task_id="t1",
            source_id="web1",
            url="https://example.com",
            success=True,
            status_code=200,
            latency_ms=150,
            data={"key": "value"},
            error_type=None,
        )
        self.assertTrue(result.success)
        self.assertIsNone(result.error_type)

    def test_failed_result(self):
        """A failed result should carry the error_type."""
        result = ScrapeResult(
            task_id="t1",
            source_id="web1",
            url="https://example.com",
            success=False,
            status_code=429,
            latency_ms=50,
            data=None,
            error_type="HTTP_429",
        )
        self.assertFalse(result.success)
        self.assertEqual(result.error_type, "HTTP_429")


class TestMetricsSnapshot(unittest.TestCase):
    """Verify MetricsSnapshot dataclass creation."""

    def test_create_snapshot(self):
        """Snapshot should store all aggregated metric fields."""
        snap = MetricsSnapshot(
            window_secs=30,
            total_requests=100,
            success_count=90,
            timeout_count=5,
            conn_error_count=2,
            http_429_count=3,
            http_403_count=0,
            ip_ban_suspected_count=0,
            avg_latency_ms=200.5,
            timestamp=1000000.0,
        )
        self.assertEqual(snap.total_requests, 100)
        self.assertEqual(snap.success_count, 90)
        self.assertEqual(snap.avg_latency_ms, 200.5)


if __name__ == "__main__":
    unittest.main()
