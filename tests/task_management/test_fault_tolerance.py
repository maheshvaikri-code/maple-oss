"""Tests for maple.task_management.fault_tolerance - FaultTolerantExecutor."""

import pytest
from unittest.mock import MagicMock
from maple.task_management.task_queue import TaskQueue, TaskPriority
from maple.task_management.fault_tolerance import (
    FaultTolerantExecutor, FaultTolerancePolicy, FailureType, RetryStrategy
)


@pytest.fixture
def task_queue():
    tq = TaskQueue(max_queue_size=100)
    tq.start()
    yield tq
    tq.stop()


@pytest.fixture
def executor(task_queue):
    scheduler = MagicMock()
    return FaultTolerantExecutor(task_queue, scheduler)


class TestExecutorLifecycle:
    """Test executor start/stop."""

    def test_start_stop(self, executor):
        executor.start_executor()
        executor.stop_executor()


class TestFailureHandling:
    """Test task failure handling."""

    def test_handle_agent_failure(self, executor, task_queue):
        result = task_queue.submit_task("compute", {"data": 1}, priority=TaskPriority.NORMAL)
        task_id = result.unwrap()

        handle_result = executor.handle_task_failure(
            task_id, "worker_1", FailureType.AGENT_FAILURE, "Agent crashed"
        )
        assert handle_result is not None

    def test_handle_timeout(self, executor, task_queue):
        result = task_queue.submit_task("compute", {"data": 1}, priority=TaskPriority.NORMAL)
        task_id = result.unwrap()

        handle_result = executor.handle_task_failure(
            task_id, "worker_1", FailureType.TIMEOUT, "Timed out"
        )
        assert handle_result is not None


class TestCircuitBreaker:
    """Test circuit breaker functionality."""

    def test_get_circuit_breaker_status(self, executor):
        result = executor.get_circuit_breaker_status("worker_1")
        assert result is not None

    def test_reset_circuit_breaker(self, executor):
        result = executor.reset_circuit_breaker("worker_1")
        assert result is not None


class TestRecoveryHandlers:
    """Test recovery handler registration."""

    def test_register_recovery_handler(self, executor):
        called = []
        executor.register_recovery_handler(
            FailureType.AGENT_FAILURE,
            lambda task, failure: called.append(task) or True
        )

    def test_failure_callback(self, executor):
        records = []
        executor.add_failure_callback(lambda record: records.append(record))


class TestFaultTolerancePolicy:
    """Test FaultTolerancePolicy defaults."""

    def test_default_policy(self):
        policy = FaultTolerancePolicy()
        assert policy.max_retries > 0
        assert policy.base_delay > 0


class TestStatistics:
    """Test fault tolerance statistics."""

    def test_stats(self, executor):
        stats = executor.get_fault_tolerance_stats()
        assert isinstance(stats, dict)
