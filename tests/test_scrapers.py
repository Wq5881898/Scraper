"""Tests for scraper network behavior."""

import unittest
from unittest.mock import patch

from src.models import Task
from src.rate_limiter import RateLimiter
from src.scrapers import Web1Scraper


class _NoSleepBackoff:
    def get_sleep(self, attempt, error_type=None):
        return 0.0


class _DummyResponse:
    status_code = 200

    def json(self):
        return {"data": {"ok": True}}


class _FakeSession:
    def __init__(self, outcomes):
        self._outcomes = list(outcomes)
        self.request_calls = 0
        self.close_calls = 0

    def request(self, **kwargs):
        self.request_calls += 1
        outcome = self._outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome

    def close(self):
        self.close_calls += 1


class TestWeb1SessionLifecycle(unittest.TestCase):
    def _make_scraper(self, max_retries=3):
        return Web1Scraper(
            rate_limiter=RateLimiter(qps=0.0),
            backoff=_NoSleepBackoff(),
            max_retries=max_retries,
            timeout=1,
        )

    def _make_task(self):
        return Task(task_id="t1", source_id="web1", url="https://example.com")

    def test_fetch_closes_session_on_success(self):
        fake_session = _FakeSession([_DummyResponse()])
        scraper = self._make_scraper()
        with patch("src.scrapers.curl_requests.Session", return_value=fake_session):
            scraper.fetch(self._make_task())
        self.assertEqual(fake_session.request_calls, 1)
        self.assertEqual(fake_session.close_calls, 1)

    def test_fetch_closes_session_across_retries(self):
        fake_session = _FakeSession([TimeoutError("x"), _DummyResponse()])
        scraper = self._make_scraper(max_retries=3)
        with patch("src.scrapers.curl_requests.Session", return_value=fake_session):
            with patch("src.scrapers._time.sleep", return_value=None):
                scraper.fetch(self._make_task())
        self.assertEqual(fake_session.request_calls, 2)
        self.assertEqual(fake_session.close_calls, 2)


if __name__ == "__main__":
    unittest.main()
