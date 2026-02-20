from __future__ import annotations

import random
from typing import Optional


class BackoffStrategy:
    """Exponential backoff with jitter for retry delays.

    Computes sleep duration as base * 2^(attempt-1) plus random jitter,
    capped at a configurable maximum."""

    def __init__(self, base_seconds: float = 0.5, max_seconds: float = 10.0) -> None:
        self._base = base_seconds
        self._max = max_seconds

    def get_sleep(self, attempt: int, error_type: Optional[str] = None) -> float:
        """Calculate the backoff sleep duration in seconds for a given retry attempt."""
        exp = min(self._max, self._base * (2 ** max(attempt - 1, 0)))
        jitter = random.uniform(0, exp * 0.1)
        return exp + jitter
