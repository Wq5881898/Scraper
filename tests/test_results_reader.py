from __future__ import annotations

import json
import os
import tempfile
import unittest

from src.results_reader import read_recent_records, summarize_results


class TestResultsReader(unittest.TestCase):
    def _write_jsonl(self, rows: list[dict], invalid_line: str = "") -> str:
        fd, path = tempfile.mkstemp(suffix=".jsonl")
        os.close(fd)
        with open(path, "w", encoding="utf-8") as f:
            for row in rows:
                f.write(json.dumps(row) + "\n")
            if invalid_line:
                f.write(invalid_line + "\n")
        return path

    def test_summarize_results_works_for_mixed_shapes(self) -> None:
        rows = [
            {"source_id": "web1", "success": True, "latency_ms": 100, "status_code": 200},
            {"source_id": "web1", "status": False, "latency": 300, "status_code": 500},
            {"source_id": "web2", "status": True, "latency": 200, "status_code": 200},
        ]
        path = self._write_jsonl(rows, invalid_line="not json")
        try:
            summary = summarize_results(path)
            self.assertEqual(summary["total_records"], 3)
            self.assertEqual(summary["invalid_lines"], 1)
            self.assertEqual(summary["overall"]["successes"], 2)
            self.assertEqual(summary["overall"]["failures"], 1)
            self.assertAlmostEqual(summary["overall"]["avg_latency_ms"], 200.0)

            sources = {item["source_id"]: item for item in summary["by_source"]}
            self.assertEqual(sources["web1"]["total"], 2)
            self.assertEqual(sources["web1"]["successes"], 1)
            self.assertEqual(sources["web1"]["failures"], 1)
            self.assertEqual(sources["web2"]["total"], 1)
        finally:
            os.remove(path)

    def test_read_recent_records_respects_limit(self) -> None:
        rows = [{"source_id": "web1", "status": True, "latency": i} for i in range(10)]
        path = self._write_jsonl(rows)
        try:
            result = read_recent_records(path, limit=3)
            self.assertEqual(result["limit"], 3)
            self.assertEqual(len(result["records"]), 3)
            self.assertEqual(result["records"][0]["latency"], 7)
            self.assertEqual(result["records"][-1]["latency"], 9)
        finally:
            os.remove(path)


if __name__ == "__main__":
    unittest.main()
