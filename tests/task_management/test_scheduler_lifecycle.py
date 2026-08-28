"""Regression tests for scheduler assignment and rollback lifecycle."""

import threading
from unittest.mock import MagicMock

from maple.core.result import Result
from maple.task_management.scheduler import SchedulingPolicy, TaskScheduler
from maple.task_management.task_queue import TaskQueue, TaskStatus


def _scheduler(task_queue, agents, policy=None):
    registry = MagicMock()
    registry.list_agents.return_value = agents
    matcher = MagicMock()
    matcher.match_capabilities.return_value = Result.ok([])
    return TaskScheduler(task_queue, registry, matcher, policy=policy)


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


def test_scheduler_assignment_respects_capacity_under_concurrency():
    task_queue = TaskQueue(max_queue_size=2)
    task_queue.start()
    try:
        agent = MagicMock(agent_id="worker-1", capabilities=[])
        scheduler = _scheduler(
            task_queue,
            [agent],
            SchedulingPolicy(max_concurrent_per_agent=1),
        )
        first_id = task_queue.submit_task("compute", {}).unwrap()
        second_id = task_queue.submit_task("compute", {}).unwrap()
        first = task_queue.get_task(first_id).unwrap()
        second = task_queue.get_task(second_id).unwrap()
        barrier = threading.Barrier(2)
        results = [None, None]

        def assign(index, task):
            barrier.wait()
            results[index] = scheduler._assign_task_to_agent(task, "worker-1")

        threads = [
            threading.Thread(target=assign, args=(0, first)),
            threading.Thread(target=assign, args=(1, second)),
        ]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=2.0)

        assert sum(result.is_ok() for result in results) == 1
        assert sum(result.is_err() for result in results) == 1
        assert scheduler.get_agent_load("worker-1") == 1
        statuses = {
            task_queue.get_task(task_id).unwrap().status for task_id in (first_id, second_id)
        }
        assert statuses == {TaskStatus.ASSIGNED, TaskStatus.QUEUED}
    finally:
        task_queue.stop()


def test_queue_completion_accepts_running_owned_task_and_records_result():
    task_queue = TaskQueue(max_queue_size=1)
    task_queue.start()
    try:
        task_id = task_queue.submit_task("compute", {}).unwrap()
        dequeued = task_queue.get_next_task().unwrap()
        assert dequeued is not None
        assert task_queue.assign_task(task_id, "worker-1").is_ok()
        assert task_queue.update_task_status(task_id, TaskStatus.RUNNING).is_ok()

        result = task_queue.complete_task(
            task_id, "worker-1", result={"value": 42}
        )

        assert result.is_ok()
        completed = task_queue.get_task(task_id).unwrap()
        assert completed.status == TaskStatus.COMPLETED
        assert completed.result == {"value": 42}
    finally:
        task_queue.stop()


def test_queue_reassignment_rejects_running_task_without_changing_owner():
    task_queue = TaskQueue(max_queue_size=1)
    task_queue.start()
    try:
        task_id = task_queue.submit_task("compute", {}).unwrap()
        assert task_queue.get_next_task().is_ok()
        assert task_queue.assign_task(task_id, "worker-1").is_ok()
        assert task_queue.update_task_status(task_id, TaskStatus.RUNNING).is_ok()

        result = task_queue.reassign_task(task_id, "worker-1", "worker-2")

        assert result.is_err()
        assert "running" in result.unwrap_err()
        task = task_queue.get_task(task_id).unwrap()
        assert task.assigned_agent == "worker-1"
        assert task.status == TaskStatus.RUNNING
    finally:
        task_queue.stop()
