"""Tests for the BackoffStrategy class."""

import unittest

from src.backoff import BackoffStrategy


class TestBackoffStrategy(unittest.TestCase):
    """Verify exponential backoff produces correct sleep durations."""

    def test_first_attempt_returns_base(self):
        """First retry should sleep approximately the base duration."""
        backoff = BackoffStrategy(base_seconds=1.0, max_seconds=30.0)
        sleep = backoff.get_sleep(attempt=1)
        # base * 2^0 = 1.0, plus up to 10% jitter
        self.assertGreaterEqual(sleep, 1.0)
        self.assertLessEqual(sleep, 1.1)

    def test_exponential_growth(self):
        """Each subsequent attempt should roughly double the sleep time."""
        backoff = BackoffStrategy(base_seconds=0.5, max_seconds=100.0)
        sleep_1 = backoff.get_sleep(attempt=1)
        sleep_2 = backoff.get_sleep(attempt=2)
        sleep_3 = backoff.get_sleep(attempt=3)
        # Without jitter: 0.5, 1.0, 2.0
        self.assertLess(sleep_1, sleep_2)
        self.assertLess(sleep_2, sleep_3)

    def test_respects_max_seconds(self):
        """Sleep duration should never exceed max_seconds (plus jitter)."""
        backoff = BackoffStrategy(base_seconds=1.0, max_seconds=5.0)
        sleep = backoff.get_sleep(attempt=20)
        # max is 5.0 + up to 10% jitter = 5.5
        self.assertLessEqual(sleep, 5.5)

    def test_jitter_is_non_negative(self):
        """Jitter component should never produce a negative sleep value."""
        backoff = BackoffStrategy(base_seconds=0.1, max_seconds=1.0)
        for attempt in range(1, 10):
            sleep = backoff.get_sleep(attempt)
            self.assertGreater(sleep, 0)


class TestBackoffWithErrorType(unittest.TestCase):
    """Verify that error_type parameter is accepted without breaking."""

    def test_error_type_does_not_crash(self):
        """Passing an error_type should not raise an exception."""
        backoff = BackoffStrategy()
        sleep = backoff.get_sleep(attempt=1, error_type="TimeoutError")
        self.assertGreater(sleep, 0)


if __name__ == "__main__":
    unittest.main()
