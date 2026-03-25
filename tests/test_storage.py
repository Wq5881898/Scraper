"""Tests for JSONL storage behavior."""

import json
import tempfile
import unittest
from pathlib import Path

from src.models import ScrapeResult
from src.storage import JsonlStorage


def _make_result(i: int) -> ScrapeResult:
    return ScrapeResult(
        task_id=f"task-{i}",
        source_id="web2",
        url="https://example.com",
        success=(i % 2 == 0),
        status_code=200 if i % 2 == 0 else 500,
        latency_ms=100 + i,
        data={"i": i},
        error_type=None if i % 2 == 0 else "HTTP_500",
    )


class TestJsonlStorage(unittest.TestCase):
    def test_close_flushes_all_items(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "results.jsonl"
            storage = JsonlStorage(str(path))
            for i in range(25):
                storage.write(_make_result(i))
            storage.close()

            lines = path.read_text(encoding="utf-8").strip().splitlines()
            self.assertEqual(len(lines), 25)

    def test_writes_canonical_and_compat_fields(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "results.jsonl"
            storage = JsonlStorage(str(path))
            storage.write(_make_result(1))
            storage.close()

            record = json.loads(path.read_text(encoding="utf-8").strip())
            self.assertIn("success", record)
            self.assertIn("latency_ms", record)
            self.assertIn("status", record)
            self.assertIn("latency", record)
            self.assertEqual(record["success"], record["status"])
            self.assertEqual(record["latency_ms"], record["latency"])


if __name__ == "__main__":
    unittest.main()
