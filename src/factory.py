from __future__ import annotations

from .base import BaseScraper
from .metrics import MetricsCollector
from .rate_limiter import RateLimiter
from .backoff import BackoffStrategy
from .models import Task
from .scrapers import Web1Scraper, Web2Scraper


class ScraperFactory:
    """Factory for creating scraper instances based on task configuration.

    NOTE: Keep behaviour stable.
    - No caching.
    - Each task creates a scraper instance just like your original design.
    """

    def __init__(
        self,
        metrics: MetricsCollector,
        rate_limiter: RateLimiter,
        backoff: BackoffStrategy,
    ) -> None:
        self._metrics = metrics
        self._rate_limiter = rate_limiter
        self._backoff = backoff

    def create_scraper(self, task: Task) -> BaseScraper:
        if task.source_id == "web1":
            return Web1Scraper(
                metrics=self._metrics,
                rate_limiter=self._rate_limiter,
                backoff=self._backoff,
            )
        if task.source_id == "web2":
            return Web2Scraper(
                metrics=self._metrics,
                rate_limiter=self._rate_limiter,
                backoff=self._backoff,
            )
        raise ValueError(f"Unknown source_id: {task.source_id}")