from __future__ import annotations

import json
import time
from typing import Iterable, Optional

from .metrics import MetricsCollector
from .models import MetricsSnapshot
from .strategies import ControlStrategy
from .controller import ThreadPoolController


class SmartController:
    """Periodically evaluates runtime metrics and applies adaptive control strategies.

    Runs in a background thread and adjusts system behaviour (e.g. concurrency)
    based on aggregated metrics over a sliding time window."""

    def __init__(
        self,
        metrics: MetricsCollector,
        controller: ThreadPoolController,
        strategies: Iterable[ControlStrategy],
        eval_interval_secs: int = 10,
        window_secs: int = 30,
    ) -> None:
        self._metrics = metrics
        self._controller = controller
        self._strategies = list(strategies)
        self._eval_interval = eval_interval_secs
        self._window_secs = window_secs
        self._running = False

    def start(self) -> None:
        """Begin the periodic evaluation loop (blocking; run in a daemon thread)."""
        self._running = True
        while self._running:
            snapshot = self._metrics.snapshot(self._window_secs)
            self._apply_strategies(snapshot)
            time.sleep(self._eval_interval)

    def stop(self) -> None:
        """Signal the evaluation loop to stop after the current cycle."""
        self._running = False

    def _apply_strategies(self, snapshot: MetricsSnapshot) -> None:
        """Evaluate each strategy in priority order and apply the first matching one."""
        for strat in self._strategies:
            if strat.should_apply(snapshot):
                old_limit = self._controller.limit
                strat.apply(self._controller, snapshot)
                new_limit = self._controller.limit
                log = {
                    "timestamp": time.time(),
                    "strategy": strat.__class__.__name__,
                    "old_limit": old_limit,
                    "new_limit": new_limit,
                    "reason": {
                        "window_secs": snapshot.window_secs,
                        "total_requests": snapshot.total_requests,
                        "timeout_count": snapshot.timeout_count,
                        "http_429_count": snapshot.http_429_count,
                        "http_403_count": snapshot.http_403_count,
                        "avg_latency_ms": snapshot.avg_latency_ms,
                        "ip_ban_suspected": snapshot.ip_ban_suspected_count > 0,
                    },
                }
                print(json.dumps(log, ensure_ascii=False))
                break
