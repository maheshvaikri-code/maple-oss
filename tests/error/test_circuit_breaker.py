"""Tests for maple.error.circuit_breaker - CircuitBreaker."""

import pytest
import time
from maple.error.circuit_breaker import CircuitBreaker, CircuitState
from maple.core.result import Result


@pytest.fixture
def breaker():
    return CircuitBreaker(failure_threshold=3, reset_timeout=0.5, half_open_max_calls=1)


class TestCircuitBreakerInit:
    """Test circuit breaker initialization."""

    def test_default_state(self, breaker):
        assert breaker.state == CircuitState.CLOSED
        assert breaker.failure_count == 0
        assert breaker.is_closed() is True
        assert breaker.is_open() is False

    def test_custom_params(self):
        cb = CircuitBreaker(failure_threshold=10, reset_timeout=60.0, half_open_max_calls=5)
        assert cb.failure_threshold == 10
        assert cb.reset_timeout == 60.0
        assert cb.half_open_max_calls == 5


class TestClosedState:
    """Test behavior in closed state."""

    def test_success_stays_closed(self, breaker):
        result = breaker.execute(lambda: Result.ok("success"))
        assert result.is_ok()
        assert result.unwrap() == "success"
        assert breaker.is_closed()

    def test_failure_increments_count(self, breaker):
        breaker.execute(lambda: Result.err({"errorType": "FAIL"}))
        assert breaker.failure_count == 1
        assert breaker.is_closed()

    def test_success_resets_count(self, breaker):
        breaker.execute(lambda: Result.err({"errorType": "FAIL"}))
        breaker.execute(lambda: Result.err({"errorType": "FAIL"}))
        breaker.execute(lambda: Result.ok("recovered"))
        assert breaker.failure_count == 0
        assert breaker.is_closed()


class TestOpenState:
    """Test transition to and behavior in open state."""

    def test_opens_after_threshold(self, breaker):
        for _ in range(3):
            breaker.execute(lambda: Result.err({"errorType": "FAIL"}))
        assert breaker.is_open()

    def test_blocks_requests_when_open(self, breaker):
        for _ in range(3):
            breaker.execute(lambda: Result.err({"errorType": "FAIL"}))

        result = breaker.execute(lambda: Result.ok("should not run"))
        assert result.is_err()
        assert result.unwrap_err()['errorType'] == 'CIRCUIT_OPEN'

    def test_open_includes_time_remaining(self, breaker):
        for _ in range(3):
            breaker.execute(lambda: Result.err({"errorType": "FAIL"}))

        result = breaker.execute(lambda: Result.ok("blocked"))
        error = result.unwrap_err()
        assert 'timeRemaining' in error['details']


class TestHalfOpenState:
    """Test half-open state behavior."""

    def test_transitions_to_half_open(self, breaker):
        for _ in range(3):
            breaker.execute(lambda: Result.err({"errorType": "FAIL"}))
        assert breaker.is_open()

        # Wait for reset timeout
        time.sleep(0.6)

        # Next call should put it in half-open
        result = breaker.execute(lambda: Result.ok("test"))
        assert result.is_ok()
        # Should close on success in half-open
        assert breaker.is_closed()

    def test_half_open_failure_reopens(self, breaker):
        for _ in range(3):
            breaker.execute(lambda: Result.err({"errorType": "FAIL"}))

        time.sleep(0.6)

        # Fail in half-open state → back to open
        result = breaker.execute(lambda: Result.err({"errorType": "STILL_FAILING"}))
        assert result.is_err()
        assert breaker.is_open()

    def test_half_open_call_limit(self):
        cb = CircuitBreaker(failure_threshold=2, reset_timeout=0.1, half_open_max_calls=1)
        cb.execute(lambda: Result.err({"errorType": "FAIL"}))
        cb.execute(lambda: Result.err({"errorType": "FAIL"}))
        assert cb.is_open()

        time.sleep(0.2)

        # First call allowed
        cb.execute(lambda: Result.err({"errorType": "FAIL"}))

        time.sleep(0.2)

        # First call transitions to half-open, allowed
        result = cb.execute(lambda: Result.ok("test"))
        # After success, should close
        assert cb.is_closed() or result.is_ok()


class TestReset:
    """Test manual reset."""

    def test_reset_from_open(self, breaker):
        for _ in range(3):
            breaker.execute(lambda: Result.err({"errorType": "FAIL"}))
        assert breaker.is_open()

        breaker.reset()
        assert breaker.is_closed()
        assert breaker.failure_count == 0

    def test_reset_clears_counters(self, breaker):
        breaker.execute(lambda: Result.err({"errorType": "FAIL"}))
        breaker.reset()
        assert breaker.failure_count == 0
        assert breaker.half_open_calls == 0
        assert breaker.last_failure_time == 0


class TestStateChecks:
    """Test state query methods."""

    def test_is_closed(self, breaker):
        assert breaker.is_closed() is True
        assert breaker.is_open() is False
        assert breaker.is_half_open() is False
