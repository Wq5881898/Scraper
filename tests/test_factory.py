"""Tests for the ScraperFactory class."""

import unittest

from src.backoff import BackoffStrategy
from src.factory import ScraperFactory
from src.metrics import MetricsCollector
from src.models import Task
from src.rate_limiter import RateLimiter
from src.scrapers import Web1Scraper, Web2Scraper


class TestScraperFactory(unittest.TestCase):
    """Verify that the factory creates the correct scraper type."""

    def setUp(self):
        """Set up shared factory instance."""
        self.factory = ScraperFactory(
            metrics=MetricsCollector(),
            rate_limiter=RateLimiter(qps=1.0),
            backoff=BackoffStrategy(),
        )

    def test_creates_web1_scraper(self):
        """source_id 'web1' should produce a Web1Scraper instance."""
        task = Task(task_id="t1", source_id="web1", url="https://example.com")
        scraper = self.factory.create_scraper(task)
        self.assertIsInstance(scraper, Web1Scraper)

    def test_creates_web2_scraper(self):
        """source_id 'web2' should produce a Web2Scraper instance."""
        task = Task(task_id="t2", source_id="web2", url="https://example.com")
        scraper = self.factory.create_scraper(task)
        self.assertIsInstance(scraper, Web2Scraper)

    def test_unknown_source_raises_error(self):
        """An unrecognized source_id should raise ValueError."""
        task = Task(task_id="t3", source_id="unknown", url="https://example.com")
        with self.assertRaises(ValueError) as ctx:
            self.factory.create_scraper(task)
        self.assertIn("unknown", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
