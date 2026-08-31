"""Adversarial coverage for trusted local task execution."""

import threading

import pytest

from maple.autonomy.execution import CancellationToken, ExecutionPolicy
from maple.core.result import Result
from maple.task_management import (
    FileTaskQueue,
    TaskQueue,
    TaskStatus,
    TrustedTaskWorker,
)


def test_trusted_task_worker_rejects_invalid_configuration():
    queue = TaskQueue()

    with pytest.raises(ValueError):
        TrustedTaskWorker(queue, "", {})
    with pytest.raises(TypeError):
        TrustedTaskWorker(queue, "worker-a", {"compute": "not-callable"})
    with pytest.raises(ValueError):
        TrustedTaskWorker(queue, "worker-a", {"\x00": lambda payload: payload})
    with pytest.raises(ValueError):
        TrustedTaskWorker(queue, "worker-a", {"line\nbreak": lambda payload: payload})
    with pytest.raises(TypeError):
        TrustedTaskWorker(queue, "worker-a", {}, capabilities="gpu")
    with pytest.raises(ValueError, match="maximum number"):
        TrustedTaskWorker(
            queue, "worker-a", {}, capabilities=(str(i) for i in range(129))
        )
    with pytest.raises(ValueError):
        TrustedTaskWorker(queue, "worker-a", {}, max_task_timeout_seconds=0)
    with pytest.raises(ValueError):
        TrustedTaskWorker(
            queue,
            "worker-a",
            {},
            execution_policy=ExecutionPolicy(timeout_seconds=0),
        )


def test_trusted_task_worker_filters_unregistered_task_types():
    queue = TaskQueue(max_queue_size=2)
    queue.start()
    try:
        unknown_id = queue.submit_task("unknown", {}).unwrap()
        known_id = queue.submit_task("known", {}).unwrap()
        worker = TrustedTaskWorker(
            queue, "worker-a", {"known": lambda payload: {"ok": True}}
        )

        completed = worker.run_once().unwrap()

        assert completed is not None
        assert completed.task_id == known_id
        assert queue.get_task(unknown_id).unwrap().status == TaskStatus.QUEUED
    finally:
        queue.stop()


def test_trusted_task_worker_respects_capability_filter():
    queue = TaskQueue(max_queue_size=1)
    queue.start()
    try:
        task_id = queue.submit_task("compute", {}, requirements=["gpu"]).unwrap()
        worker = TrustedTaskWorker(
            queue, "worker-a", {"compute": lambda payload: payload}
        )

        result = worker.run_once()

        assert result.is_ok()
        assert result.unwrap() is None
        assert queue.get_task(task_id).unwrap().status == TaskStatus.QUEUED
    finally:
        queue.stop()


def test_task_queue_rejects_malformed_task_type_filter_without_mutation():
    queue = TaskQueue(max_queue_size=1)
    queue.start()
    try:
        task_id = queue.submit_task("compute", {}).unwrap()

        result = queue.get_next_task(task_types=[None], timeout_seconds=0)

        assert result.is_err()
        assert "task_types" in result.unwrap_err()
        assert queue.get_task(task_id).unwrap().status == TaskStatus.QUEUED
    finally:
        queue.stop()


def test_task_queue_rejects_string_task_type_filter_without_mutation():
    queue = TaskQueue(max_queue_size=1)
    queue.start()
    try:
        task_id = queue.submit_task("compute", {}).unwrap()

        result = queue.get_next_task(task_types="compute", timeout_seconds=0)

        assert result.is_err()
        assert queue.get_task(task_id).unwrap().status == TaskStatus.QUEUED
    finally:
        queue.stop()


def test_task_queue_bounds_task_type_filter_without_mutation():
    queue = TaskQueue(max_queue_size=1)
    queue.start()
    try:
        task_id = queue.submit_task("compute", {}).unwrap()

        result = queue.get_next_task(
            task_types=[f"task-{index}" for index in range(257)], timeout_seconds=0
        )

        assert result.is_err()
        assert "at most 256" in result.unwrap_err()
        assert queue.get_task(task_id).unwrap().status == TaskStatus.QUEUED
    finally:
        queue.stop()


def test_trusted_task_worker_completes_in_memory_task():
    queue = TaskQueue(max_queue_size=1)
    queue.start()
    original_payload = {"value": 2}
    task_id = queue.submit_task("add", original_payload).unwrap()
    seen = []

    def add(payload):
        seen.append(dict(payload))
        payload["value"] = 3
        return {"value": payload["value"] + 1}

    try:
        worker = TrustedTaskWorker(queue, "worker-a", {"add": add})
        completed = worker.run_once().unwrap()

        assert completed is not None
        assert completed.status == TaskStatus.COMPLETED
        assert completed.assigned_agent == "worker-a"
        assert completed.result == {"value": 4}
        assert seen == [{"value": 2}]
        assert original_payload == {"value": 2}
        assert queue.get_task(task_id).unwrap().payload == {"value": 2}
    finally:
        queue.stop()


def test_trusted_task_worker_completes_file_task(tmp_path):
    path = tmp_path / "tasks.json"
    queue = FileTaskQueue(path)
    queue.start()
    task_id = queue.submit_task("persist", {"value": 7}).unwrap()
    worker = TrustedTaskWorker(
        queue, "worker-a", {"persist": lambda payload: {"value": payload["value"]}}
    )

    completed = worker.run_once().unwrap()
    assert completed is not None
    assert completed.status == TaskStatus.COMPLETED
    queue.stop()

    restored = FileTaskQueue(path)
    persisted = restored.get_task(task_id).unwrap()
    assert persisted.status == TaskStatus.COMPLETED
    assert persisted.result == {"value": 7}
    restored.stop()


def test_trusted_task_worker_records_handler_failure_without_raw_exception():
    queue = TaskQueue(max_queue_size=1)
    queue.start()
    task_id = queue.submit_task("explode", {}).unwrap()
    calls = []

    def explode(payload):
        calls.append(payload)
        raise RuntimeError("secret-value-must-not-be-stored")

    try:
        worker = TrustedTaskWorker(queue, "worker-a", {"explode": explode})
        failed = worker.run_once().unwrap()

        assert failed is not None
        assert failed.status == TaskStatus.FAILED
        assert failed.error == "Task execution failed with EXECUTION_ERROR."
        assert "secret-value" not in failed.error
        assert len(calls) == 1
        assert queue.get_task(task_id).unwrap().status == TaskStatus.FAILED
    finally:
        queue.stop()


def test_trusted_task_worker_records_handler_result_error():
    queue = TaskQueue(max_queue_size=1)
    queue.start()
    try:
        task_id = queue.submit_task("reject", {}).unwrap()
        worker = TrustedTaskWorker(
            queue,
            "worker-a",
            {
                "reject": lambda payload: Result.err(
                    {"errorType": "HANDLER_REJECTED", "message": "private"}
                )
            },
        )

        failed = worker.run_once().unwrap()

        assert failed is not None
        assert failed.status == TaskStatus.FAILED
        assert failed.error == "Task execution failed with TASK_HANDLER_ERROR."
        assert queue.get_task(task_id).unwrap().result is None
    finally:
        queue.stop()


def test_trusted_task_worker_does_not_store_handler_error_type_metadata():
    queue = TaskQueue(max_queue_size=1)
    queue.start()
    try:
        task_id = queue.submit_task("reject", {}).unwrap()
        worker = TrustedTaskWorker(
            queue,
            "worker-a",
            {
                "reject": lambda payload: Result.err(
                    {"errorType": "private-secret", "message": "private"}
                )
            },
        )

        failed = worker.run_once().unwrap()

        assert failed is not None
        assert failed.status == TaskStatus.FAILED
        assert failed.error == "Task execution failed with TASK_HANDLER_ERROR."
        assert "private-secret" not in failed.error
        assert queue.get_task(task_id).unwrap().status == TaskStatus.FAILED
    finally:
        queue.stop()


def test_trusted_task_worker_rejects_invalid_task_timeout():
    queue = TaskQueue(max_queue_size=1)
    queue.start()
    invoked = []

    try:
        task_id = queue.submit_task("invalid-timeout", {}, timeout_seconds=0).unwrap()
        worker = TrustedTaskWorker(
            queue,
            "worker-a",
            {"invalid-timeout": lambda payload: invoked.append(payload)},
        )

        failed = worker.run_once().unwrap()

        assert failed is not None
        assert failed.status == TaskStatus.FAILED
        assert failed.error == (
            "Task timeout must be finite, positive, and within the worker limit."
        )
        assert invoked == []
        assert queue.get_task(task_id).unwrap().status == TaskStatus.FAILED
    finally:
        queue.stop()


def test_trusted_task_worker_enforces_output_bound():
    queue = TaskQueue(max_queue_size=1)
    queue.start()
    try:
        task_id = queue.submit_task("large", {}).unwrap()
        worker = TrustedTaskWorker(
            queue,
            "worker-a",
            {"large": lambda payload: "x" * 100},
            execution_policy=ExecutionPolicy(max_output_bytes=8),
        )

        failed = worker.run_once().unwrap()

        assert failed is not None
        assert failed.status == TaskStatus.FAILED
        assert failed.error == "Task execution failed with EXECUTION_OUTPUT_TOO_LARGE."
        assert queue.get_task(task_id).unwrap().result is None
    finally:
        queue.stop()


def test_trusted_task_worker_rejects_non_json_result():
    queue = TaskQueue(max_queue_size=1)
    queue.start()
    try:
        task_id = queue.submit_task("non-json", {}).unwrap()
        worker = TrustedTaskWorker(
            queue, "worker-a", {"non-json": lambda payload: object()}
        )

        failed = worker.run_once().unwrap()

        assert failed is not None
        assert failed.status == TaskStatus.FAILED
        assert failed.error == "Task execution failed with EXECUTION_NON_JSON_VALUE."
        assert queue.get_task(task_id).unwrap().result is None
    finally:
        queue.stop()


def test_trusted_task_worker_records_timeout_failure():
    queue = TaskQueue(max_queue_size=1)
    queue.start()
    release = threading.Event()
    try:
        task_id = queue.submit_task("slow", {}).unwrap()

        def slow_handler(payload):
            release.wait(timeout=2)
            return payload

        worker = TrustedTaskWorker(
            queue,
            "worker-a",
            {"slow": slow_handler},
            execution_policy=ExecutionPolicy(timeout_seconds=0.01),
        )

        failed = worker.run_once().unwrap()

        assert failed is not None
        assert failed.status == TaskStatus.FAILED
        assert failed.error == "Task execution failed with EXECUTION_TIMEOUT."
        assert queue.get_task(task_id).unwrap().status == TaskStatus.FAILED
    finally:
        release.set()
        queue.stop()


def test_trusted_task_worker_cancellation_preserves_or_cancels_lifecycle():
    queue = TaskQueue(max_queue_size=2)
    queue.start()
    try:
        before_id = queue.submit_task("cancel-before", {}).unwrap()
        before = CancellationToken()
        before.cancel()
        worker = TrustedTaskWorker(
            queue, "worker-a", {"cancel-before": lambda payload: payload}
        )

        rejected = worker.run_once(cancellation=before)

        assert rejected.is_err()
        assert queue.get_task(before_id).unwrap().status == TaskStatus.QUEUED

        queue.cancel_task(before_id)
        during_id = queue.submit_task("cancel-during", {}).unwrap()
        during = CancellationToken()
        started = threading.Event()
        outcome = []

        def cooperative_handler(payload):
            started.set()
            while not during.wait(timeout=0.05):
                pass
            return payload

        worker = TrustedTaskWorker(
            queue, "worker-a", {"cancel-during": cooperative_handler}
        )
        thread = threading.Thread(
            target=lambda: outcome.append(worker.run_once(cancellation=during))
        )
        thread.start()
        assert started.wait(timeout=2)
        during.cancel()
        thread.join(timeout=2)

        assert not thread.is_alive()
        assert len(outcome) == 1
        cancelled = outcome[0].unwrap()
        assert cancelled is not None
        assert cancelled.status == TaskStatus.CANCELLED
        assert queue.get_task(during_id).unwrap().status == TaskStatus.CANCELLED
    finally:
        queue.stop()


def test_trusted_task_worker_poll_bounds_and_empty_result():
    queue = TaskQueue()
    queue.start()
    try:
        worker = TrustedTaskWorker(
            queue, "worker-a", {"compute": lambda payload: payload}
        )
        empty = worker.run_once()

        assert empty.is_ok()
        assert empty.unwrap() is None
        assert worker.run_once(timeout_seconds=0.01).unwrap() is None
        assert worker.run_once(timeout_seconds=60.01).is_err()
        assert worker.run_once(timeout_seconds=float("nan")).is_err()
    finally:
        queue.stop()


def test_trusted_task_worker_rejects_concurrent_invocation():
    queue = TaskQueue(max_queue_size=1)
    queue.start()
    release = threading.Event()
    started = threading.Event()
    outcome = []

    def blocking_handler(payload):
        started.set()
        release.wait(timeout=2)
        return payload

    try:
        queue.submit_task("blocking", {"ok": True}).unwrap()
        worker = TrustedTaskWorker(queue, "worker-a", {"blocking": blocking_handler})
        thread = threading.Thread(target=lambda: outcome.append(worker.run_once()))
        thread.start()
        assert started.wait(timeout=2)

        busy = worker.run_once()

        assert busy.is_err()
        assert "already executing" in busy.unwrap_err()
        release.set()
        thread.join(timeout=2)
        assert not thread.is_alive()
        assert outcome[0].unwrap().status == TaskStatus.COMPLETED
    finally:
        release.set()
        queue.stop()
