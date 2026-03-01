"""Tests for maple.error.recovery - retry and backoff functions."""

import pytest
from maple.error.recovery import retry, RetryOptions, exponential_backoff
from maple.core.result import Result


class TestRetryOptions:
    """Test RetryOptions dataclass."""

    def test_defaults(self):
        opts = RetryOptions()
        assert opts.max_attempts == 3
        assert opts.retryable_errors is None

    def test_custom_options(self):
        opts = RetryOptions(max_attempts=5, retryable_errors=["TIMEOUT"])
        assert opts.max_attempts == 5
        assert opts.retryable_errors == ["TIMEOUT"]


class TestRetry:
    """Test retry function."""

    def test_success_on_first_try(self):
        call_count = [0]
        def func():
            call_count[0] += 1
            return Result.ok("success")

        opts = RetryOptions(max_attempts=3, backoff=lambda a: 0)
        result = retry(func, opts)
        assert result.is_ok()
        assert result.unwrap() == "success"
        assert call_count[0] == 1

    def test_success_after_retries(self):
        call_count = [0]
        def func():
            call_count[0] += 1
            if call_count[0] < 3:
                return Result.err({"errorType": "TRANSIENT"})
            return Result.ok("recovered")

        opts = RetryOptions(max_attempts=5, backoff=lambda a: 0)
        result = retry(func, opts)
        assert result.is_ok()
        assert result.unwrap() == "recovered"
        assert call_count[0] == 3

    def test_all_attempts_fail(self):
        call_count = [0]
        def func():
            call_count[0] += 1
            return Result.err({"errorType": "PERSISTENT"})

        opts = RetryOptions(max_attempts=3, backoff=lambda a: 0)
        result = retry(func, opts)
        assert result.is_err()
        assert call_count[0] == 3

    def test_non_retryable_error_stops_early(self):
        call_count = [0]
        def func():
            call_count[0] += 1
            return Result.err({"errorType": "FATAL"})

        opts = RetryOptions(
            max_attempts=5,
            backoff=lambda a: 0,
            retryable_errors=["TIMEOUT", "TRANSIENT"]
        )
        result = retry(func, opts)
        assert result.is_err()
        assert call_count[0] == 1  # Stopped after first non-retryable

    def test_retryable_error_continues(self):
        call_count = [0]
        def func():
            call_count[0] += 1
            if call_count[0] < 3:
                return Result.err({"errorType": "TIMEOUT"})
            return Result.ok("success")

        opts = RetryOptions(
            max_attempts=5,
            backoff=lambda a: 0,
            retryable_errors=["TIMEOUT"]
        )
        result = retry(func, opts)
        assert result.is_ok()
        assert call_count[0] == 3

    def test_single_attempt(self):
        call_count = [0]
        def func():
            call_count[0] += 1
            return Result.err({"errorType": "FAIL"})

        opts = RetryOptions(max_attempts=1, backoff=lambda a: 0)
        result = retry(func, opts)
        assert result.is_err()
        assert call_count[0] == 1


class TestExponentialBackoff:
    """Test exponential backoff function generator."""

    def test_basic_backoff(self):
        backoff = exponential_backoff(initial=1.0, factor=2.0, jitter=0)
        assert backoff(0) == 1.0
        assert backoff(1) == 2.0
        assert backoff(2) == 4.0
        assert backoff(3) == 8.0

    def test_with_jitter(self):
        backoff = exponential_backoff(initial=1.0, factor=2.0, jitter=0.5)
        # With jitter, value should be between base and base * 1.5
        for _ in range(10):
            delay = backoff(1)
            assert 2.0 <= delay <= 3.0  # 2.0 + up to 50% jitter

    def test_no_jitter(self):
        backoff = exponential_backoff(initial=0.5, factor=3.0, jitter=0)
        assert backoff(0) == 0.5
        assert backoff(1) == 1.5
        assert backoff(2) == 4.5

    def test_custom_initial(self):
        backoff = exponential_backoff(initial=0.01, factor=2.0, jitter=0)
        assert backoff(0) == 0.01
        assert backoff(1) == 0.02
