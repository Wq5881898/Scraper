from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass(frozen=True)
class Task:
    task_id: str
    source_id: str
    url: str
    params: Dict[str, Any] = field(default_factory=dict)
    meta: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ScrapeResult:
    task_id: str
    source_id: str
    url: str
    success: bool
    status_code: Optional[int]
    latency_ms: int
    data: Optional[Any]
    error_type: Optional[str]


@dataclass(frozen=True)
class MetricsSnapshot:
    window_secs: int
    total_requests: int
    success_count: int
    timeout_count: int
    conn_error_count: int
    http_429_count: int
    http_403_count: int
    ip_ban_suspected_count: int
    avg_latency_ms: float
    timestamp: float
