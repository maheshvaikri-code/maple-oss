"""Regression tests for scheduler assignment and rollback lifecycle."""

from unittest.mock import MagicMock

from maple.core.result import Result
from maple.task_management.scheduler import TaskScheduler
from maple.task_management.task_queue import TaskQueue, TaskStatus


def _scheduler(task_queue, agents):
    registry = MagicMock()
    registry.list_agents.return_value = agents
    matcher = MagicMock()
    matcher.match_capabilities.return_value = Result.ok([])
    return TaskScheduler(task_queue, registry, matcher)


def test_scheduler_failure_requeues_physical_task():
    task_queue = TaskQueue(max_queue_size=2)
    task_queue.start()
    try:
        scheduler = _scheduler(task_queue, [])
        task_id = task_queue.submit_task("compute", {}).unwrap()
        task = task_queue.get_next_task().unwrap()

        assert task.task_id == task_id
        assert task.status == TaskStatus.ASSIGNED

        result = scheduler._return_failed_task_to_queue(task_id, "no agents")

        assert result.is_ok()
        restored = task_queue.get_task(task_id).unwrap()
        assert restored.status == TaskStatus.QUEUED
        assert restored.retry_count == 1
        assert task_queue.get_next_task().unwrap().task_id == task_id
    finally:
        task_queue.stop()


def test_scheduler_rejects_duplicate_assignment():
    task_queue = TaskQueue(max_queue_size=2)
    task_queue.start()
    try:
        agent = MagicMock(agent_id="worker-1", capabilities=[])
        scheduler = _scheduler(task_queue, [agent])
        task_id = task_queue.submit_task("compute", {}).unwrap()

        first = scheduler.schedule_task(task_id)
        second = scheduler.schedule_task(task_id)

        assert first.is_ok()
        assert second.is_err()
        assert "already assigned" in second.unwrap_err()
    finally:
        task_queue.stop()


def test_queue_assignment_claim_is_atomic_for_scheduler():
    task_queue = TaskQueue(max_queue_size=2)
    task_queue.start()
    try:
        scheduler = _scheduler(task_queue, [])
        task_id = task_queue.submit_task("compute", {}).unwrap()
        task = task_queue.get_next_task().unwrap()

        first = scheduler._assign_task_to_agent(task, "worker-1")
        second = scheduler._assign_task_to_agent(task, "worker-2")

        assert first.is_ok()
        assert second.is_err()
        assert task_queue.get_task(task_id).unwrap().assigned_agent == "worker-1"
    finally:
        task_queue.stop()


def test_queue_assignment_rejects_empty_agent():
    task_queue = TaskQueue(max_queue_size=1)
    task_id = task_queue.submit_task("compute", {}).unwrap()

    result = task_queue.assign_task(task_id, "")

    assert result.is_err()
    assert result.unwrap_err() == "Assigned agent cannot be empty"
    assert task_queue.get_task(task_id).unwrap().status == TaskStatus.QUEUED
