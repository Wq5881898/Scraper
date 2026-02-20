from __future__ import annotations

from typing import Dict

from .base import BaseScraper
from .metrics import MetricsCollector
from .rate_limiter import RateLimiter
from .backoff import BackoffStrategy
from .models import Task
from .scrapers import Web1Scraper, Web2Scraper


class ScraperFactory:
    """Factory for creating scraper instances based on task configuration.

    Improvements:
    - Caches instances to avoid per-task object construction overhead.
    - Web2Scraper is safe to share (stateless besides dependencies).
    - Web1Scraper defaults to per-call instance to avoid session/thread-safety surprises,
      but we still keep the option to cache if you later decide it's safe.
    """

    def __init__(
        self,
        metrics: MetricsCollector,
        rate_limiter: RateLimiter,
        backoff: BackoffStrategy,
        cache_web1: bool = False,
        cache_web2: bool = True,
    ) -> None:
        self._metrics = metrics
        self._rate_limiter = rate_limiter
        self._backoff = backoff
        self._cache_web1 = cache_web1
        self._cache_web2 = cache_web2
        self._cache: Dict[str, BaseScraper] = {}

    def create_scraper(self, task: Task) -> BaseScraper:
        source = task.source_id

        # Decide caching per source
        cache_allowed = (source == "web1" and self._cache_web1) or (source == "web2" and self._cache_web2)
        if cache_allowed and source in self._cache:
            return self._cache[source]

        if source == "web1":
            scraper: BaseScraper = Web1Scraper(
                metrics=self._metrics,
                rate_limiter=self._rate_limiter,
                backoff=self._backoff,
            )
        elif source == "web2":
            scraper = Web2Scraper(
                metrics=self._metrics,
                rate_limiter=self._rate_limiter,
                backoff=self._backoff,
            )
        else:
            raise ValueError(f"Unknown source_id: {source}")

        if cache_allowed:
            self._cache[source] = scraper
        return scraper