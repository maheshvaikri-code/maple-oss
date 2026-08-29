"""
Copyright (C) 2025 Mahesh Vaijainthymala Krishnamoorthy (Mahesh Vaikri)

This file is part of MAPLE - Multi Agent Protocol Language Engine.

MAPLE - Multi Agent Protocol Language Engine is free software: you can redistribute it and/or
modify it under the terms of the GNU Affero General Public License as published by the Free Software
Foundation, either version 3 of the License, or (at your option) any later version.
"""

import json
from unittest.mock import MagicMock

import pytest

from maple.core.result import Result
from maple.resources.lease import FileLeaseManager
from maple.task_management import FileTaskQueue
from maple.task_management.scheduler import TaskScheduler
from maple.task_management.task_queue import TaskPriority, TaskStatus


def _queue_path(tmp_path):
    return tmp_path / "tasks.json"


def test_file_task_queue_exports_and_recovers_queued_tasks(tmp_path):
    path = _queue_path(tmp_path)
    queue = FileTaskQueue(path)
    queue.start()
    low_id = queue.submit_task("low", {}, priority=TaskPriority.LOW).unwrap()
    critical_id = queue.submit_task(
        "critical", {"value": 1}, priority=TaskPriority.CRITICAL
    ).unwrap()
    queue.stop()

    restored = FileTaskQueue(path)
    restored.start()
    critical = restored.get_next_task(timeout_seconds=0).unwrap()
    assert critical is not None
    assert critical.task_id == critical_id
    assert critical.status == TaskStatus.ASSIGNED
    assert restored.assign_task(critical_id, "agent-a").is_ok()
    completed = restored.complete_task(
        critical_id, "agent-a", result={"accepted": True}
    ).unwrap()
    assert completed.status == TaskStatus.COMPLETED

    low = restored.get_next_task(timeout_seconds=0).unwrap()
    assert low is not None
    assert low.task_id == low_id
    restored.stop()

    final = FileTaskQueue(path)
    assert final.get_task(critical_id).unwrap().status == TaskStatus.COMPLETED
    final.stop()


def test_file_task_queue_requeues_inflight_work_after_restart(tmp_path):
    path = _queue_path(tmp_path)
    queue = FileTaskQueue(path)
    queue.start()
    task_id = queue.submit_task("recoverable", {}).unwrap()
    claimed = queue.get_next_task(timeout_seconds=0).unwrap()
    assert claimed is not None
    assert claimed.task_id == task_id
    assert claimed.status == TaskStatus.ASSIGNED
    queue.stop()

    restored = FileTaskQueue(path)
    restored.start()
    recovered = restored.get_next_task(timeout_seconds=0).unwrap()
    assert recovered is not None
    assert recovered.task_id == task_id
    assert recovered.status == TaskStatus.ASSIGNED
    assert recovered.assigned_agent is None
    restored.stop()


def test_file_task_queue_rejects_malformed_state_without_replacing_it(tmp_path):
    path = _queue_path(tmp_path)
    path.write_bytes(b"{not-json")

    with pytest.raises(ValueError, match="malformed"):
        FileTaskQueue(path)

    assert path.read_bytes() == b"{not-json"


def test_file_task_queue_rejects_unknown_state_fields(tmp_path):
    path = _queue_path(tmp_path)
    path.write_text(
        json.dumps({"version": 1, "tasks": [], "unexpected": True}),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="fields"):
        FileTaskQueue(path)


def test_file_task_queue_rejects_unsupported_json_and_oversized_tasks(tmp_path):
    path = _queue_path(tmp_path)
    queue = FileTaskQueue(path, max_task_bytes=256)
    baseline = path.read_bytes()

    unsupported = queue.submit_task("unsupported", {"value": {1, 2}})
    assert unsupported.is_err()
    assert path.read_bytes() == baseline
    assert queue.list_tasks() == []

    oversized = queue.submit_task("oversized", {"value": "x" * 1_000})
    assert oversized.is_err()
    assert path.read_bytes() == baseline
    assert queue.list_tasks() == []
    queue.stop()


def test_file_task_queue_fails_closed_when_another_holder_has_the_fence(tmp_path):
    path = _queue_path(tmp_path)
    queue = FileTaskQueue(path)
    lock_root = tmp_path / ".tasks.json.locks"
    other = FileLeaseManager(lock_root)
    held = other.acquire("task-queue", "other-process", 30)
    assert held.is_ok()
    baseline = path.read_bytes()

    try:
        rejected = queue.submit_task("blocked", {})
        assert rejected.is_err()
        assert "fence" in rejected.unwrap_err().lower()
        assert path.read_bytes() == baseline
    finally:
        assert other.release(held.unwrap()).is_ok()
        queue.stop()


def test_file_task_queue_instances_share_fenced_state(tmp_path):
    path = _queue_path(tmp_path)
    first = FileTaskQueue(path)
    second = FileTaskQueue(path)

    first_id = first.submit_task("first", {}).unwrap()
    second_id = second.submit_task("second", {}).unwrap()

    assert {task.task_id for task in first.list_tasks()} == {first_id, second_id}
    assert {task.task_id for task in second.list_tasks()} == {first_id, second_id}
    first.stop()
    second.stop()


def test_file_task_queue_rolls_back_memory_when_persistence_fails(tmp_path):
    path = _queue_path(tmp_path)
    queue = FileTaskQueue(path)
    baseline = path.read_bytes()
    original_persist = queue._persist
    queue._persist = lambda state: Result.err("simulated disk failure")

    try:
        rejected = queue.submit_task("not-committed", {})
        assert rejected.is_err()
        assert "disk failure" in rejected.unwrap_err()
    finally:
        queue._persist = original_persist
        queue.stop()

    assert path.read_bytes() == baseline
    restored = FileTaskQueue(path)
    assert restored.list_tasks() == []
    restored.stop()


def test_file_task_queue_validates_constructor_bounds(tmp_path):
    path = _queue_path(tmp_path)
    with pytest.raises(ValueError):
        FileTaskQueue(path, max_tasks=0)
    with pytest.raises(ValueError):
        FileTaskQueue(path, max_task_bytes=0)
    with pytest.raises(ValueError):
        FileTaskQueue(path, max_state_bytes=0)
    with pytest.raises(ValueError):
        FileTaskQueue(path, lease_ttl_seconds=0)


def test_task_scheduler_can_use_file_task_queue(tmp_path):
    path = _queue_path(tmp_path)
    queue = FileTaskQueue(path)
    queue.start()
    agent = MagicMock(agent_id="agent-a", capabilities=["compute"])
    match = MagicMock(agent_id="agent-a", availability_score=1.0)
    registry = MagicMock()
    registry.list_agents.return_value = [agent]
    matcher = MagicMock()
    matcher.match_capabilities.return_value = Result.ok([match])
    scheduler = TaskScheduler(queue, registry, matcher)
    task_id = queue.submit_task("compute", {}, requirements=["compute"]).unwrap()

    assert scheduler.schedule_task(task_id).unwrap() == "agent-a"
    assigned = queue.get_task(task_id).unwrap()
    assert assigned.status == TaskStatus.ASSIGNED
    assert assigned.assigned_agent == "agent-a"
    queue.stop()


def test_file_task_queue_persists_terminal_error_and_metadata(tmp_path):
    path = _queue_path(tmp_path)
    queue = FileTaskQueue(path)
    queue.start()
    task_id = queue.submit_task(
        "failable", {"input": "x"}, metadata={"trace_id": "trace-1"}
    ).unwrap()
    task = queue.get_next_task(timeout_seconds=0).unwrap()
    assert task is not None
    assert queue.assign_task(task_id, "agent-a").is_ok()
    failed = queue.fail_task(task_id, "agent-a", "temporary failure").unwrap()
    assert failed.status == TaskStatus.FAILED
    queue.stop()

    restored = FileTaskQueue(path)
    persisted = restored.get_task(task_id).unwrap()
    assert persisted.status == TaskStatus.FAILED
    assert persisted.error == "temporary failure"
    assert persisted.metadata == {"trace_id": "trace-1"}
    raw = json.loads(path.read_text(encoding="utf-8"))
    assert raw["version"] == 1
    assert raw["tasks"][0]["status"] == TaskStatus.FAILED.value
    restored.stop()


def test_file_task_queue_owner_safe_cancellation(tmp_path):
    path = _queue_path(tmp_path)
    queue = FileTaskQueue(path)
    queue.start()
    task_id = queue.submit_task("owned", {}).unwrap()
    assert queue.assign_task(task_id, "worker-a").is_ok()

    wrong_owner = queue.cancel_task(task_id, "worker-b")
    cancelled = queue.cancel_task(task_id, "worker-a")
    assert wrong_owner.is_err()
    assert cancelled.is_ok()
    assert cancelled.unwrap().status == TaskStatus.CANCELLED

    terminal_id = queue.submit_task("terminal", {}).unwrap()
    assert queue.assign_task(terminal_id, "worker-a").is_ok()
    assert queue.complete_task(terminal_id, "worker-a").is_ok()
    terminal_cancel = queue.cancel_task(terminal_id, "worker-a")
    assert terminal_cancel.is_err()
    queue.stop()

    restored = FileTaskQueue(path)
    assert restored.get_task(task_id).unwrap().status == TaskStatus.CANCELLED
    assert restored.get_task(terminal_id).unwrap().status == TaskStatus.COMPLETED
    restored.stop()


def test_file_task_queue_owner_safe_start_persists_and_recovers(tmp_path):
    path = _queue_path(tmp_path)
    queue = FileTaskQueue(path)
    queue.start()
    task_id = queue.submit_task("running", {}).unwrap()
    assert queue.assign_task(task_id, "worker-a").is_ok()

    wrong_owner = queue.start_task(task_id, "worker-b")
    started = queue.start_task(task_id, "worker-a")
    persisted = queue.get_task(task_id).unwrap()
    queue.stop()

    assert wrong_owner.is_err()
    assert started.is_ok()
    assert started.unwrap().status == TaskStatus.RUNNING
    assert persisted.status == TaskStatus.RUNNING
    assert persisted.started_at is not None

    restored = FileTaskQueue(path)
    recovered = restored.get_task(task_id).unwrap()
    assert recovered.status == TaskStatus.QUEUED
    assert recovered.assigned_agent is None
    restored.stop()


def test_file_task_queue_owner_safe_retry(tmp_path):
    path = _queue_path(tmp_path)
    queue = FileTaskQueue(path)
    queue.start()
    task_id = queue.submit_task("retryable", {}, max_retries=1).unwrap()
    assert queue.assign_task(task_id, "worker-a").is_ok()
    assert queue.fail_task(task_id, "worker-a", "temporary").is_ok()

    assert queue.requeue_task(task_id, "worker-b").is_err()
    retried = queue.requeue_task(task_id, "worker-a")
    assert retried.is_ok()
    updated = queue.get_task(task_id).unwrap()
    assert updated.status == TaskStatus.QUEUED
    assert updated.retry_count == 1
    assert updated.assigned_agent is None
    assert queue.requeue_task(task_id, "worker-a").is_err()

    assert queue.assign_task(task_id, "worker-a").is_ok()
    assert queue.fail_task(task_id, "worker-a", "still temporary").is_ok()
    assert queue.requeue_task(task_id, "worker-a").is_err()
    queue.stop()

    restored = FileTaskQueue(path)
    assert restored.get_task(task_id).unwrap().status == TaskStatus.FAILED
    restored.stop()
