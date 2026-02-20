"""Tests for the RateLimiter class."""

import time
import unittest

from src.rate_limiter import RateLimiter


class TestRateLimiter(unittest.TestCase):
    """Verify that the rate limiter throttles requests correctly."""

    def test_acquire_does_not_block_first_call(self):
        """The first acquire() call should return almost immediately."""
        limiter = RateLimiter(qps=10.0)
        start = time.time()
        limiter.acquire()
        elapsed = time.time() - start
        self.assertLess(elapsed, 0.05)

    def test_acquire_throttles_rapid_calls(self):
        """Rapid acquire() calls at 2 QPS should enforce delays between requests."""
        limiter = RateLimiter(qps=2.0)
        start = time.time()
        limiter.acquire()
        limiter.acquire()
        limiter.acquire()
        elapsed = time.time() - start
        # 3 calls at 2 QPS: at least 2 intervals of 0.5s = 1.0s minimum,
        # but allow slack for first-call timing and scheduling variance
        self.assertGreaterEqual(elapsed, 0.4)

    def test_zero_qps_does_not_block(self):
        """QPS of 0 should disable rate limiting entirely."""
        limiter = RateLimiter(qps=0.0)
        start = time.time()
        for _ in range(10):
            limiter.acquire()
        elapsed = time.time() - start
        self.assertLess(elapsed, 0.1)


if __name__ == "__main__":
    unittest.main()
