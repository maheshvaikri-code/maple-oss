# Copyright (C) 2025 Mahesh Vaijainthymala Krishnamoorthy
# (Mahesh Vaikri)
#
# This file is part of MAPLE - Multi Agent Protocol Language Engine.
#
# MAPLE - Multi Agent Protocol Language Engine is free software: you can
# redistribute it and/or modify it under the terms of the GNU Affero General
# Public License as published by the Free Software Foundation, either version 3
# of the License, or (at your option) any later version.
# MAPLE - Multi Agent Protocol Language Engine is distributed in the hope that
# it will be useful, but WITHOUT ANY WARRANTY; without even the implied warranty
# of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU Affero
# General Public License for more details. You should have received a copy of
# the GNU Affero General Public License along with MAPLE - Multi Agent Protocol
# Language Engine. If not, see <https://www.gnu.org/licenses/>.
"""The circuit breaker's reset window must survive a clock correction (ADR-163).

Measured before the fix, with a 30s window: a +1h step let a call straight
through, and a -1h step held the circuit open while reporting 3599.8 seconds
remaining against a configured 1 second.
"""

import time

import pytest

import maple.error.circuit_breaker as cb_module
from maple.core.result import Result
from maple.error.circuit_breaker import CircuitBreaker, CircuitState


def fail():
    return Result.err({"errorType": "BOOM", "message": "downstream is down"})


def ok():
    return Result.ok("fine")


@pytest.fixture
def steppable_clock(monkeypatch):
    """Step the wall clock the way NTP does, leaving the real clock alone."""
    offset = {"seconds": 0.0}
    real = time.time
    monkeypatch.setattr(
        cb_module.time, "time", lambda: real() + offset["seconds"], raising=False
    )
    return offset


def tripped(reset_timeout):
    breaker = CircuitBreaker(failure_threshold=2, reset_timeout=reset_timeout)
    for _ in range(2):
        breaker.execute(fail)
    assert breaker.state == CircuitState.OPEN
    return breaker


class TestResetWindowSurvivesClockSteps:
    def test_a_forward_step_does_not_skip_the_window(self, steppable_clock):
        """The window exists to stop hammering a failing dependency. An NTP
        correction must not hand out the very call it was blocking."""
        breaker = tripped(30.0)
        assert breaker.execute(ok).is_err()

        steppable_clock["seconds"] = 3600.0
        assert breaker.execute(ok).is_err(), "a +1h clock step skipped the window"

    def test_a_backward_step_does_not_hold_the_circuit_open(self, steppable_clock):
        """A recovered dependency must not stay cut off for an hour."""
        breaker = tripped(0.2)
        steppable_clock["seconds"] = -3600.0
        time.sleep(0.3)
        assert breaker.execute(ok).is_ok(), "a -1h clock step held the circuit open"

    def test_time_remaining_stays_sane_across_a_step(self, steppable_clock):
        breaker = tripped(30.0)
        steppable_clock["seconds"] = -3600.0
        result = breaker.execute(ok)
        assert result.is_err()
        remaining = result.unwrap_err()["details"]["timeRemaining"]
        assert 0 < remaining <= 30.0, (
            "timeRemaining should never exceed the configured window; "
            f"got {remaining}"
        )

    def test_should_allow_agrees_with_execute_across_a_step(self, steppable_clock):
        breaker = tripped(30.0)
        steppable_clock["seconds"] = 3600.0
        assert breaker.should_allow() is False

    def test_the_window_still_elapses_on_real_time(self, steppable_clock):
        """The fix must not simply freeze the breaker open forever."""
        breaker = tripped(0.2)
        assert breaker.execute(ok).is_err()
        time.sleep(0.3)
        assert breaker.execute(ok).is_ok()


class TestTheObservableRecordIsUnchanged:
    """last_failure_time is a public property on FailureDetector and
    fault_tolerance, and appears in a get_statistics() dict that now reaches
    the metrics exporter. It must stay an epoch value (ADR-163)."""

    def test_last_failure_time_is_still_wall_clock(self):
        breaker = CircuitBreaker(failure_threshold=1, reset_timeout=5.0)
        before = time.time()
        breaker.record_failure()
        after = time.time()
        assert before <= breaker.last_failure_time <= after

    def test_it_is_an_epoch_not_seconds_since_boot(self):
        breaker = CircuitBreaker(failure_threshold=1, reset_timeout=5.0)
        breaker.record_failure()
        # ~1.7e9 is 2023; a perf_counter reading would be far smaller
        assert breaker.last_failure_time > 1.7e9

    def test_the_discovery_wrapper_property_still_reports_an_epoch(self):
        """CircuitBreakerState re-exports the field for backwards
        compatibility, so the change must not leak through it either."""
        from maple.discovery.failure_detector import CircuitBreakerState

        wrapper = CircuitBreakerState("agent-1", threshold=1)
        wrapper._cb.record_failure()
        assert wrapper.last_failure_time > 1.7e9

    def test_the_fault_tolerance_wrapper_still_reports_an_epoch(self):
        """fault_tolerance surfaces the same field in a get_statistics()
        dict, which now reaches the metrics exporter (ADR-162)."""
        from maple.task_management.fault_tolerance import CircuitBreakerState

        wrapper = CircuitBreakerState("agent-1", threshold=1)
        wrapper._cb.record_failure()
        assert wrapper.last_failure_time > 1.7e9
        # the derived record stays wall clock and self-consistent
        assert wrapper.next_attempt_time > 1.7e9

    def test_reset_clears_both_clocks(self):
        breaker = CircuitBreaker(failure_threshold=1, reset_timeout=60.0)
        breaker.record_failure()
        breaker.reset()
        assert breaker.last_failure_time == 0
        assert breaker.state == CircuitState.CLOSED
        # with no failure recorded the window reads as long elapsed, not as
        # a duration measured from zero
        assert breaker.should_allow() is True


class TestCallersDoNotReDeriveTheWindow:
    """The breaker measuring monotonically is undone if a caller recomputes
    the window from last_failure_time + reset_timeout on the wall clock."""

    def test_the_wrapper_exposes_a_monotonic_window_check(self):
        from maple.task_management.fault_tolerance import CircuitBreakerState

        wrapper = CircuitBreakerState("agent-1", threshold=1, timeout=30.0)
        wrapper._cb.record_failure()
        assert wrapper.reset_window_elapsed is False

    def test_the_window_check_is_immune_to_a_wall_clock_step(self, steppable_clock):
        from maple.task_management.fault_tolerance import CircuitBreakerState

        wrapper = CircuitBreakerState("agent-1", threshold=1, timeout=30.0)
        wrapper._cb.record_failure()
        steppable_clock["seconds"] = 3600.0
        assert (
            wrapper.reset_window_elapsed is False
        ), "a wall-clock step reopened the window"

    def test_the_executor_loop_does_not_compare_wall_clock_deadlines(self):
        import inspect

        from maple.task_management.fault_tolerance import FaultTolerantExecutor

        source = inspect.getsource(FaultTolerantExecutor._executor_loop)
        assert (
            "next_attempt_time" not in source
        ), "the loop re-derives the reset window from wall-clock fields"
        assert "reset_window_elapsed" in source

    def test_a_short_window_still_elapses(self):
        from maple.task_management.fault_tolerance import CircuitBreakerState

        wrapper = CircuitBreakerState("agent-1", threshold=1, timeout=0.15)
        wrapper._cb.record_failure()
        time.sleep(0.25)
        assert wrapper.reset_window_elapsed is True


class TestNoFailureRecorded:
    def test_a_fresh_breaker_reports_infinite_elapsed(self):
        breaker = CircuitBreaker(failure_threshold=1, reset_timeout=60.0)
        assert breaker._since_last_failure() == float("inf")

    def test_elapsed_is_measured_from_the_failure_not_from_zero(self):
        breaker = CircuitBreaker(failure_threshold=1, reset_timeout=60.0)
        breaker.record_failure()
        assert breaker._since_last_failure() < 1.0
