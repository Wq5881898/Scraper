from __future__ import annotations

import json
from typing import Any


def _to_bool(value: Any, *, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"true", "1", "yes", "y"}:
            return True
        if lowered in {"false", "0", "no", "n"}:
            return False
    return default


def _to_float(value: Any) -> float | None:
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return None
        try:
            return float(stripped)
        except ValueError:
            return None
    return None


def _extract_success(row: dict[str, Any]) -> bool:
    if "success" in row:
        return _to_bool(row["success"])
    if "status" in row:
        return _to_bool(row["status"])

    status_code = _to_float(row.get("status_code"))
    if status_code is None:
        return False
    return 200 <= status_code < 400


def _extract_latency_ms(row: dict[str, Any]) -> float:
    latency = _to_float(row.get("latency_ms"))
    if latency is None:
        latency = _to_float(row.get("latency"))
    return latency if latency is not None else 0.0


def iter_results(path: str) -> tuple[list[dict[str, Any]], int]:
    rows: list[dict[str, Any]] = []
    invalid_lines = 0

    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            text = line.strip()
            if not text:
                continue
            try:
                parsed = json.loads(text)
            except json.JSONDecodeError:
                invalid_lines += 1
                continue
            if isinstance(parsed, dict):
                rows.append(parsed)
            else:
                invalid_lines += 1

    return rows, invalid_lines


def summarize_results(path: str) -> dict[str, Any]:
    rows, invalid_lines = iter_results(path)
    if not rows:
        return {
            "path": path,
            "total_records": 0,
            "invalid_lines": invalid_lines,
            "overall": {
                "successes": 0,
                "failures": 0,
                "success_rate_pct": 0.0,
                "avg_latency_ms": 0.0,
                "min_latency_ms": 0.0,
                "max_latency_ms": 0.0,
            },
            "by_source": [],
        }

    by_source: dict[str, dict[str, Any]] = {}
    total_success = 0
    total_fail = 0
    all_latencies: list[float] = []

    for row in rows:
        source_id = str(row.get("source_id", "unknown"))
        success = _extract_success(row)
        latency = _extract_latency_ms(row)

        all_latencies.append(latency)
        if success:
            total_success += 1
        else:
            total_fail += 1

        if source_id not in by_source:
            by_source[source_id] = {
                "source_id": source_id,
                "total": 0,
                "successes": 0,
                "failures": 0,
                "avg_latency_ms": 0.0,
                "min_latency_ms": 0.0,
                "max_latency_ms": 0.0,
            }

        current = by_source[source_id]
        current["total"] += 1
        if success:
            current["successes"] += 1
        else:
            current["failures"] += 1

        if current["total"] == 1:
            current["min_latency_ms"] = latency
            current["max_latency_ms"] = latency
            current["avg_latency_ms"] = latency
        else:
            current["min_latency_ms"] = min(current["min_latency_ms"], latency)
            current["max_latency_ms"] = max(current["max_latency_ms"], latency)
            previous_avg = current["avg_latency_ms"]
            current["avg_latency_ms"] = previous_avg + (latency - previous_avg) / current["total"]

    total = len(rows)
    overall_avg = sum(all_latencies) / total if total else 0.0
    by_source_list = sorted(by_source.values(), key=lambda item: item["source_id"])
    for item in by_source_list:
        item["success_rate_pct"] = (item["successes"] / item["total"] * 100.0) if item["total"] else 0.0

    return {
        "path": path,
        "total_records": total,
        "invalid_lines": invalid_lines,
        "overall": {
            "successes": total_success,
            "failures": total_fail,
            "success_rate_pct": (total_success / total * 100.0) if total else 0.0,
            "avg_latency_ms": overall_avg,
            "min_latency_ms": min(all_latencies) if all_latencies else 0.0,
            "max_latency_ms": max(all_latencies) if all_latencies else 0.0,
        },
        "by_source": by_source_list,
    }


def read_recent_records(path: str, limit: int = 20) -> dict[str, Any]:
    rows, invalid_lines = iter_results(path)
    valid_limit = max(1, min(limit, 500))
    return {
        "path": path,
        "limit": valid_limit,
        "invalid_lines": invalid_lines,
        "records": rows[-valid_limit:],
    }
