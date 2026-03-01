"""Extended tests for the shared CircuitBreaker (record_failure, record_success, should_allow)."""

import time
import pytest
from maple.error.circuit_breaker import CircuitBreaker, CircuitState
from maple.core.result import Result


class TestRecordFailure:
    def test_record_failure_increments(self):
        cb = CircuitBreaker(failure_threshold=3)
        cb.record_failure()
        assert cb.failure_count == 1
        assert cb.state == CircuitState.CLOSED

    def test_record_failure_opens_circuit(self):
        cb = CircuitBreaker(failure_threshold=3)
        cb.record_failure()
        cb.record_failure()
        cb.record_failure()
        assert cb.state == CircuitState.OPEN

    def test_record_failure_in_half_open_reopens(self):
        cb = CircuitBreaker(failure_threshold=2, reset_timeout=0.01)
        cb.record_failure()
        cb.record_failure()  # Opens
        assert cb.state == CircuitState.OPEN
        time.sleep(0.02)
        # Trigger half-open via should_allow
        cb.should_allow()
        assert cb.state == CircuitState.HALF_OPEN
        cb.record_failure()
        assert cb.state == CircuitState.OPEN


class TestRecordSuccess:
    def test_record_success_resets_count(self):
        cb = CircuitBreaker(failure_threshold=5)
        cb.record_failure()
        cb.record_failure()
        assert cb.failure_count == 2
        cb.record_success()
        assert cb.failure_count == 0

    def test_record_success_in_half_open_closes(self):
        cb = CircuitBreaker(failure_threshold=2, reset_timeout=0.01)
        cb.record_failure()
        cb.record_failure()
        time.sleep(0.02)
        cb.should_allow()  # Transition to half-open
        assert cb.state == CircuitState.HALF_OPEN
        cb.record_success()
        assert cb.state == CircuitState.CLOSED
        assert cb.failure_count == 0


class TestShouldAllow:
    def test_allows_when_closed(self):
        cb = CircuitBreaker()
        assert cb.should_allow() is True

    def test_blocks_when_open(self):
        cb = CircuitBreaker(failure_threshold=1, reset_timeout=10.0)
        cb.record_failure()
        assert cb.state == CircuitState.OPEN
        assert cb.should_allow() is False

    def test_transitions_to_half_open_after_timeout(self):
        cb = CircuitBreaker(failure_threshold=1, reset_timeout=0.01)
        cb.record_failure()
        assert cb.state == CircuitState.OPEN
        time.sleep(0.02)
        assert cb.should_allow() is True
        assert cb.state == CircuitState.HALF_OPEN

    def test_half_open_limits_calls(self):
        cb = CircuitBreaker(failure_threshold=1, reset_timeout=0.01, half_open_max_calls=1)
        cb.record_failure()
        time.sleep(0.02)
        assert cb.should_allow() is True  # First call allowed
        assert cb.should_allow() is False  # Second blocked


class TestCircuitBreakerIntegration:
    def test_full_lifecycle(self):
        cb = CircuitBreaker(failure_threshold=2, reset_timeout=0.02)

        # Start closed
        assert cb.is_closed()
        assert cb.should_allow()

        # Accumulate failures
        cb.record_failure()
        assert cb.is_closed()
        cb.record_failure()
        assert cb.is_open()

        # Blocked while open
        assert not cb.should_allow()

        # Wait for reset timeout
        time.sleep(0.03)
        assert cb.should_allow()
        assert cb.is_half_open()

        # Success closes circuit
        cb.record_success()
        assert cb.is_closed()
        assert cb.failure_count == 0
