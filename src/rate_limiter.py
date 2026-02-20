from __future__ import annotations

import threading
import time


class RateLimiter:
    """Thread-safe token-bucket rate limiter based on queries per second (QPS).

    Calling acquire() blocks the current thread until the next request
    is allowed, ensuring the system does not exceed the configured QPS."""

    def __init__(self, qps: float) -> None:
        self._interval = 1.0 / qps if qps > 0 else 0.0
        self._lock = threading.Lock()
        self._next_allowed = 0.0

    def acquire(self) -> None:
        """Block until the next request is permitted under the QPS limit."""
        if self._interval <= 0:
            return
        with self._lock:
            now = time.time()
            if now < self._next_allowed:
                time.sleep(self._next_allowed - now)
            self._next_allowed = max(self._next_allowed + self._interval, time.time())
