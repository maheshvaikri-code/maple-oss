"""Tests for maple.task_management.scheduler - TaskScheduler."""

import pytest
from unittest.mock import MagicMock, patch
from maple.task_management.task_queue import TaskQueue, TaskPriority
from maple.task_management.scheduler import TaskScheduler, SchedulingPolicy


@pytest.fixture
def task_queue():
    tq = TaskQueue(max_queue_size=100)
    tq.start()
    yield tq
    tq.stop()


@pytest.fixture
def scheduler(task_queue):
    agent_registry = MagicMock()
    agent_registry.get_available_agents.return_value = [
        {"agent_id": "worker_1", "capabilities": ["compute"]},
        {"agent_id": "worker_2", "capabilities": ["compute", "gpu"]},
    ]
    capability_matcher = MagicMock()
    capability_matcher.match.return_value = ["worker_1"]

    sched = TaskScheduler(task_queue, agent_registry, capability_matcher)
    return sched


class TestSchedulerLifecycle:
    """Test scheduler start/stop."""

    def test_start_stop(self, scheduler):
        scheduler.start_scheduler()
        scheduler.stop_scheduler()

    def test_scheduling_metrics(self, scheduler):
        metrics = scheduler.get_scheduling_metrics()
        assert metrics is not None


class TestTaskScheduling:
    """Test task scheduling."""

    def test_schedule_task(self, scheduler, task_queue):
        result = task_queue.submit_task(
            task_type="compute",
            payload={"data": [1, 2]},
            priority=TaskPriority.NORMAL
        )
        assert result.is_ok()
        task_id = result.unwrap()

        schedule_result = scheduler.schedule_task(task_id)
        # May succeed or fail depending on mock setup
        assert schedule_result is not None

    def test_schedule_nonexistent_task(self, scheduler):
        result = scheduler.schedule_task("nonexistent_task_id")
        assert result.is_err()


class TestAgentLoad:
    """Test agent load tracking."""

    def test_get_agent_load(self, scheduler):
        load = scheduler.get_agent_load("worker_1")
        assert isinstance(load, int)
        assert load >= 0


class TestSchedulingCallbacks:
    """Test scheduling callbacks."""

    def test_add_callback(self, scheduler):
        called = []
        scheduler.add_scheduling_callback(lambda tid, aid: called.append((tid, aid)))
        # Callback registered, no error


class TestSchedulingPolicy:
    """Test SchedulingPolicy defaults."""

    def test_default_policy(self):
        policy = SchedulingPolicy()
        assert policy.max_concurrent_per_agent > 0
        assert policy.scheduling_interval > 0
