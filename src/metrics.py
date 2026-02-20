from __future__ import annotations

import time
from collections import deque
from dataclasses import asdict
from threading import Lock
from typing import Deque, Dict, Iterable, List, Optional

from .models import MetricsSnapshot, ScrapeResult


class MetricsCollector:
    def __init__(self) -> None:
        self._lock = Lock()
        self._events: Deque[tuple[float, ScrapeResult]] = deque(maxlen=10000)

    def record_result(self, result: ScrapeResult) -> None:
        with self._lock:
            self._events.append((time.time(), result))

    def snapshot(self, window_secs: int) -> MetricsSnapshot:
        now = time.time()
        cutoff = now - window_secs
        with self._lock:
            events: List[ScrapeResult] = [e for ts, e in self._events if ts >= cutoff]
        total = len(events)
        success_count = sum(1 for e in events if e.success)
        timeout_count = sum(1 for e in events if e.error_type == "Timeout")
        conn_error_count = sum(1 for e in events if e.error_type == "ConnectionError")
        http_429_count = sum(1 for e in events if e.status_code == 429)
        http_403_count = sum(1 for e in events if e.status_code == 403)
        ip_ban_suspected_count = 1 if http_403_count >= 3 else 0
        avg_latency_ms = (sum(e.latency_ms for e in events) / total) if total else 0.0

        return MetricsSnapshot(
            window_secs=window_secs,
            total_requests=total,
            success_count=success_count,
            timeout_count=timeout_count,
            conn_error_count=conn_error_count,
            http_429_count=http_429_count,
            http_403_count=http_403_count,
            ip_ban_suspected_count=ip_ban_suspected_count,
            avg_latency_ms=avg_latency_ms,
            timestamp=now,
        )

    def export_json(self) -> List[Dict]:
        with self._lock:
            return [{"timestamp": ts, **asdict(e)} for ts, e in self._events]

    def export_csv_rows(self) -> Iterable[Dict]:
        with self._lock:
            for ts, e in self._events:
                yield {"timestamp": ts, **asdict(e)}
