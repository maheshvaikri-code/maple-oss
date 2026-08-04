"""Tests for exponential_backoff(max_delay=...) -- the per-attempt delay ceiling.

MAPLE improvement #1 (proposed; revalidate with owner before merge). Without a cap the
backoff grows unbounded (initial * factor ** attempt), so a large RetryOptions.max_attempts
can stall a caller that holds a resource across the backoff. `max_delay` bounds it.
"""

import pytest

from maple.core.result import Result
from maple.error.recovery import RetryOptions, exponential_backoff, retry


class TestBackoffMaxDelay:
    def test_uncapped_grows_unbounded(self):
        b = exponential_backoff(initial=0.1, factor=2.0, jitter=0.0)  # no cap
        assert b(10) == pytest.approx(0.1 * 2 ** 10)  # ~102s -- unbounded

    def test_capped_never_exceeds_max_delay(self):
        cap = 2.0
        b = exponential_backoff(initial=0.1, factor=2.0, jitter=0.0, max_delay=cap)
        assert all(b(n) <= cap for n in range(0, 30))
        assert b(30) == cap  # a huge attempt clamps exactly to the ceiling

    def test_cap_includes_jitter(self):
        cap = 1.0
        b = exponential_backoff(initial=0.5, factor=2.0, jitter=0.5, max_delay=cap)
        # jitter is applied before the clamp, so it can never push a delay over the cap
        assert all(b(n) <= cap for n in range(0, 20))

    def test_small_attempts_unaffected_by_a_generous_cap(self):
        b = exponential_backoff(initial=0.1, factor=2.0, jitter=0.0, max_delay=1000.0)
        assert b(0) == pytest.approx(0.1)
        assert b(1) == pytest.approx(0.2)

    def test_default_is_backward_compatible_no_cap(self):
        # existing callers (no max_delay) keep the prior unbounded behavior
        b = exponential_backoff()
        assert b(5) > b(0)  # still a growing delay, no crash, no clamp

    def test_retry_with_capped_backoff_keeps_the_attempt_bound(self):
        # a capped backoff changes only the per-attempt sleep, not the attempt count
        calls = {"n": 0}

        def fn():
            calls["n"] += 1
            return Result.err({"errorType": "X"})

        opts = RetryOptions(
            max_attempts=3,
            backoff=exponential_backoff(initial=0.001, factor=2.0, jitter=0.0, max_delay=0.005),
        )
        res = retry(fn, opts)
        assert res.is_err() and calls["n"] == 3
