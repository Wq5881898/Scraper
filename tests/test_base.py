"""Tests for the BaseScraper abstract class."""

import unittest

from src.base import BaseScraper
from src.models import Task


class TestBaseScraperValidation(unittest.TestCase):
    """Verify that BaseScraper.validate() catches invalid tasks."""

    def test_validate_raises_on_empty_url(self):
        """A task with an empty URL should raise ValueError."""

        class DummyScraper(BaseScraper):
            def fetch(self, task):
                return None

            def parse(self, response):
                return None

        scraper = DummyScraper()
        task = Task(task_id="t1", source_id="web1", url="")
        with self.assertRaises(ValueError) as ctx:
            scraper.validate(task)
        self.assertIn("url", str(ctx.exception).lower())

    def test_validate_passes_with_valid_url(self):
        """A task with a valid URL should not raise."""

        class DummyScraper(BaseScraper):
            def fetch(self, task):
                return None

            def parse(self, response):
                return None

        scraper = DummyScraper()
        task = Task(task_id="t1", source_id="web1", url="https://example.com")
        # Should not raise
        scraper.validate(task)


class TestBaseScraperRun(unittest.TestCase):
    """Verify that BaseScraper.run() handles exceptions gracefully."""

    def test_run_captures_exception_as_error_type(self):
        """If fetch() raises, run() should return a failed ScrapeResult."""

        class FailingScraper(BaseScraper):
            def fetch(self, task):
                raise ConnectionError("network down")

            def parse(self, response):
                return None

        scraper = FailingScraper()
        task = Task(task_id="t1", source_id="web1", url="https://example.com")
        result = scraper.run(task)
        self.assertFalse(result.success)
        self.assertEqual(result.error_type, "ConnectionError")
        self.assertIsNone(result.data)


if __name__ == "__main__":
    unittest.main()
