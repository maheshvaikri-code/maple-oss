"""
Copyright (C) 2025 Mahesh Vaijainthymala Krishnamoorthy (Mahesh Vaikri)

This file is part of MAPLE - Multi Agent Protocol Language Engine.

MAPLE - Multi Agent Protocol Language Engine is free software: you can redistribute it and/or
modify it under the terms of the GNU Affero General Public License as published by the Free Software
Foundation, either version 3 of the License, or (at your option) any later version.

Bounded atomic file-backed task admission for local restart recovery.
"""

from __future__ import annotations

import json
import math
import os
import tempfile
import time
import uuid
from pathlib import Path
from queue import PriorityQueue
from typing import Any, Callable, Dict, List, Mapping, Optional, Sequence, Union, cast

from ..core.result import Result
from ..resources.lease import FileLeaseManager, Lease
from .task_queue import QueueStats, Task, TaskPriority, TaskQueue, TaskStatus

_STATE_VERSION = 1
_MAX_DURABLE_TASKS = 100_000
_MAX_DURABLE_TASK_BYTES = 1_048_576
_MAX_DURABLE_STATE_BYTES = 64 * 1_048_576
_MAX_DURABLE_JSON_DEPTH = 16
_MAX_DURABLE_JSON_ITEMS = 10_000
_MAX_DURABLE_TEXT_LENGTH = 256
_MAX_DURABLE_TASK_ID_LENGTH = 128
_MAX_DURABLE_REQUIREMENTS = 256
_MAX_DURABLE_TIMEOUT_SECONDS = 7 * 24 * 60 * 60
_MAX_DURABLE_RETRIES = 1_000
_MAX_DURABLE_LEASE_TTL_SECONDS = 7 * 24 * 60 * 60
_DEFAULT_DURABLE_TASK_BYTES = 256 * 1_024
_DEFAULT_DURABLE_STATE_BYTES = 16 * 1_048_576
_DEFAULT_DURABLE_LEASE_TTL_SECONDS = 30.0
_DURABLE_LEASE_RESOURCE = "task-queue"
_MAX_TASK_ERROR_BYTES = 8_192


def _queue_error(message: str) -> Result[Any, str]:
    """Return a bounded public error without exposing filesystem details."""
    return Result.err(message)


def _valid_text(value: Any, *, max_length: int) -> bool:
    return (
        isinstance(value, str)
        and bool(value)
        and len(value) <= max_length
        and not any(ord(char) < 32 for char in value)
    )


def _validate_json_value(
    value: Any, *, depth: int = 0, items: int = 0
) -> Optional[str]:
    """Validate JSON-compatible values before they reach durable state."""
    if depth > _MAX_DURABLE_JSON_DEPTH:
        return "JSON value is nested too deeply."
    if value is None or isinstance(value, (bool, int, str)):
        return None
    if isinstance(value, float):
        return (
            None if math.isfinite(value) else "JSON value contains a non-finite number."
        )
    if isinstance(value, (list, tuple)):
        if items + len(value) > _MAX_DURABLE_JSON_ITEMS:
            return "JSON value contains too many items."
        for item in value:
            error = _validate_json_value(
                item, depth=depth + 1, items=items + len(value)
            )
            if error is not None:
                return error
        return None
    if isinstance(value, Mapping):
        if items + len(value) > _MAX_DURABLE_JSON_ITEMS:
            return "JSON value contains too many items."
        for key, item in value.items():
            if not _valid_text(key, max_length=_MAX_DURABLE_TEXT_LENGTH):
                return "JSON object keys must be bounded text."
            error = _validate_json_value(
                item, depth=depth + 1, items=items + len(value)
            )
            if error is not None:
                return error
        return None
    return "JSON value has an unsupported type."


def _copy_json(value: Any) -> Result[Any, str]:
    error = _validate_json_value(value)
    if error is not None:
        return Result.err(error)
    try:
        return Result.ok(
            json.loads(
                json.dumps(
                    value,
                    ensure_ascii=False,
                    allow_nan=False,
                    separators=(",", ":"),
                )
            )
        )
    except (
        TypeError,
        ValueError,
        OverflowError,
        RecursionError,
        json.JSONDecodeError,
    ):
        return Result.err("JSON value is not serializable.")


def _valid_timestamp(value: Any, *, optional: bool = True) -> bool:
    if value is None and optional:
        return True
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(float(value))
    )


class FileTaskQueue(TaskQueue):
    """A bounded, atomically persisted ``TaskQueue`` for local restarts.

    The queue is safe for concurrent local instances through a short-lived
    file-backed fencing lease around each read/modify/write operation. It is
    not a distributed worker lease or hosted scheduler. ``ASSIGNED`` and
    ``RUNNING`` tasks are returned to ``QUEUED`` during hydration, so an
    interrupted handler can be delivered again under explicit at-least-once
    semantics.
    """

    def __init__(
        self,
        path: Union[str, Path],
        max_queue_size: int = 10_000,
        *,
        max_tasks: int = 10_000,
        max_task_bytes: int = _DEFAULT_DURABLE_TASK_BYTES,
        max_state_bytes: int = _DEFAULT_DURABLE_STATE_BYTES,
        lock_timeout_seconds: float = 5.0,
        lease_ttl_seconds: float = _DEFAULT_DURABLE_LEASE_TTL_SECONDS,
    ) -> None:
        super().__init__(max_queue_size=max_queue_size)
        try:
            state_path = Path(path).expanduser().resolve()
        except (TypeError, ValueError, OSError) as exc:
            raise ValueError("path must be a valid durable queue file") from exc
        if (
            not state_path.name
            or len(state_path.name) > _MAX_DURABLE_TEXT_LENGTH
            or any(ord(char) < 32 for char in state_path.name)
        ):
            raise ValueError("path must name a bounded durable queue file")
        if (
            not isinstance(max_tasks, int)
            or isinstance(max_tasks, bool)
            or not 1 <= max_tasks <= _MAX_DURABLE_TASKS
        ):
            raise ValueError(
                f"max_tasks must be an integer from 1 to {_MAX_DURABLE_TASKS}"
            )
        if (
            not isinstance(max_task_bytes, int)
            or isinstance(max_task_bytes, bool)
            or not 1 <= max_task_bytes <= _MAX_DURABLE_TASK_BYTES
        ):
            raise ValueError(
                "max_task_bytes must be an integer from 1 to "
                f"{_MAX_DURABLE_TASK_BYTES}"
            )
        if (
            not isinstance(max_state_bytes, int)
            or isinstance(max_state_bytes, bool)
            or not 1 <= max_state_bytes <= _MAX_DURABLE_STATE_BYTES
        ):
            raise ValueError(
                "max_state_bytes must be an integer from 1 to "
                f"{_MAX_DURABLE_STATE_BYTES}"
            )
        if (
            not isinstance(lease_ttl_seconds, (int, float))
            or isinstance(lease_ttl_seconds, bool)
            or not math.isfinite(float(lease_ttl_seconds))
            or not 0 < float(lease_ttl_seconds) <= _MAX_DURABLE_LEASE_TTL_SECONDS
        ):
            raise ValueError(
                "lease_ttl_seconds must be finite and positive within the limit"
            )

        state_path.parent.mkdir(parents=True, exist_ok=True)
        self.path = state_path
        self.max_tasks = max_tasks
        self.max_task_bytes = max_task_bytes
        self.max_state_bytes = max_state_bytes
        self.lease_ttl_seconds = float(lease_ttl_seconds)
        self._holder = "queue-" + uuid.uuid4().hex
        self._lease_manager = FileLeaseManager(
            state_path.parent / ("." + state_path.name + ".locks"),
            lock_timeout_seconds=lock_timeout_seconds,
        )
        initial = self._run_durable(lambda: Result.ok(None), recover_inflight=True)
        if initial.is_err():
            raise ValueError(initial.unwrap_err())

    def start(self) -> None:
        """Enable local consumers without starting a non-durable cleanup thread."""
        with self._lock:
            if self._running:
                return
            self._running = True
            self._stop_event.clear()

    def stop(self) -> None:
        """Stop local consumers and wake any bounded waiters."""
        with self._lock:
            self._running = False
            self._condition.notify_all()
        self._stop_event.set()

    def _read_state(self) -> Result[Dict[str, Any], str]:
        if not self.path.exists():
            return Result.ok({"version": _STATE_VERSION, "tasks": []})
        try:
            raw_bytes = self.path.read_bytes()
        except (OSError, ValueError):
            return _queue_error("Durable queue state is unavailable.")
        if len(raw_bytes) > self.max_state_bytes:
            return _queue_error("Durable queue state exceeds the byte limit.")
        try:
            raw = json.loads(raw_bytes.decode("utf-8"))
        except (UnicodeDecodeError, RecursionError, json.JSONDecodeError):
            return _queue_error("Durable queue state is malformed.")
        if not isinstance(raw, dict):
            return _queue_error("Durable queue state must be an object.")
        if set(raw) != {"version", "tasks"}:
            return _queue_error("Durable queue state fields are invalid.")
        if raw.get("version") != _STATE_VERSION:
            return _queue_error("Durable queue state version is unsupported.")
        tasks = raw.get("tasks")
        if not isinstance(tasks, list) or len(tasks) > self.max_tasks:
            return _queue_error("Durable queue task count exceeds the limit.")
        return Result.ok(raw)

    def _task_from_record(self, record: Any) -> Result[Task, str]:
        if not isinstance(record, dict):
            return _queue_error("Durable queue task record must be an object.")
        required = {
            "task_id",
            "task_type",
            "payload",
            "priority",
            "requirements",
            "timeout_seconds",
            "max_retries",
            "metadata",
            "status",
            "assigned_agent",
            "created_at",
            "started_at",
            "completed_at",
            "retry_count",
            "result",
            "error",
        }
        heartbeat_required = required | {"heartbeat_at"}
        if set(record) not in (required, heartbeat_required):
            return _queue_error("Durable queue task record fields are invalid.")
        if not _valid_text(record["task_id"], max_length=_MAX_DURABLE_TASK_ID_LENGTH):
            return _queue_error("Durable queue task ID is invalid.")
        if not _valid_text(record["task_type"], max_length=_MAX_DURABLE_TEXT_LENGTH):
            return _queue_error("Durable queue task type is invalid.")
        try:
            priority = TaskPriority(record["priority"])
            status = TaskStatus(record["status"])
        except (TypeError, ValueError):
            return _queue_error("Durable queue task enum is invalid.")
        if not isinstance(record["payload"], dict) or not isinstance(
            record["metadata"], dict
        ):
            return _queue_error("Durable queue payload and metadata must be objects.")
        for value in (record["payload"], record["metadata"], record["result"]):
            if _validate_json_value(value) is not None:
                return _queue_error("Durable queue task JSON is invalid.")
        requirements = record["requirements"]
        if (
            not isinstance(requirements, list)
            or len(requirements) > _MAX_DURABLE_REQUIREMENTS
            or not all(
                _valid_text(item, max_length=_MAX_DURABLE_TEXT_LENGTH)
                for item in requirements
            )
        ):
            return _queue_error("Durable queue task requirements are invalid.")
        assigned_agent = record["assigned_agent"]
        if assigned_agent is not None and not _valid_text(
            assigned_agent, max_length=_MAX_DURABLE_TEXT_LENGTH
        ):
            return _queue_error("Durable queue task owner is invalid.")
        timeout_seconds = record["timeout_seconds"]
        max_retries = record["max_retries"]
        retry_count = record["retry_count"]
        if (
            not isinstance(timeout_seconds, int)
            or isinstance(timeout_seconds, bool)
            or not 0 <= timeout_seconds <= _MAX_DURABLE_TIMEOUT_SECONDS
            or not isinstance(max_retries, int)
            or isinstance(max_retries, bool)
            or not 0 <= max_retries <= _MAX_DURABLE_RETRIES
            or not isinstance(retry_count, int)
            or isinstance(retry_count, bool)
            or not 0 <= retry_count <= max_retries
        ):
            return _queue_error("Durable queue task retry settings are invalid.")
        if not _valid_timestamp(record["created_at"], optional=False):
            return _queue_error("Durable queue task creation time is invalid.")
        if not _valid_timestamp(record["started_at"]):
            return _queue_error("Durable queue task start time is invalid.")
        if not _valid_timestamp(record["completed_at"]):
            return _queue_error("Durable queue task completion time is invalid.")
        if not _valid_timestamp(record.get("heartbeat_at")):
            return _queue_error("Durable queue task heartbeat time is invalid.")
        error = record["error"]
        if error is not None and (
            not isinstance(error, str)
            or not error
            or len(error.encode("utf-8")) > _MAX_TASK_ERROR_BYTES
            or any(ord(char) < 32 and char not in "\r\n\t" for char in error)
        ):
            return _queue_error("Durable queue task error is invalid.")
        if (
            len(json.dumps(record, ensure_ascii=False, allow_nan=False).encode("utf-8"))
            > self.max_task_bytes
        ):
            return _queue_error("Durable queue task exceeds the byte limit.")

        started_at = record["started_at"]
        heartbeat_at = record.get("heartbeat_at")
        try:
            task = Task(
                task_id=record["task_id"],
                task_type=record["task_type"],
                payload=dict(record["payload"]),
                priority=priority,
                requirements=list(requirements),
                timeout_seconds=timeout_seconds,
                max_retries=max_retries,
                metadata=dict(record["metadata"]),
                status=status,
                assigned_agent=assigned_agent,
                created_at=float(record["created_at"]),
                started_at=(float(started_at) if started_at is not None else None),
                heartbeat_at=(
                    float(heartbeat_at) if heartbeat_at is not None else None
                ),
                completed_at=(
                    float(record["completed_at"])
                    if record["completed_at"] is not None
                    else None
                ),
                retry_count=retry_count,
                result=record["result"],
                error=error,
            )
        except (TypeError, ValueError, OverflowError, RecursionError):
            return _queue_error("Durable queue task record is invalid.")
        return Result.ok(task)

    def _hydrate(
        self, state: Mapping[str, Any], *, recover_inflight: bool = False
    ) -> Result[None, str]:
        tasks = state.get("tasks")
        if not isinstance(tasks, list):
            return _queue_error("Durable queue state tasks are invalid.")
        hydrated: Dict[str, Task] = {}
        queued_count = 0
        for record in tasks:
            task_result = self._task_from_record(record)
            if task_result.is_err():
                return Result.err(task_result.unwrap_err())
            task = task_result.unwrap()
            if recover_inflight and task.status in (
                TaskStatus.ASSIGNED,
                TaskStatus.RUNNING,
                TaskStatus.PENDING,
            ):
                task.status = TaskStatus.QUEUED
                task.assigned_agent = None
                task.started_at = None
                task.heartbeat_at = None
            if task.task_id in hydrated:
                return _queue_error("Durable queue task IDs must be unique.")
            hydrated[task.task_id] = task
            if task.status == TaskStatus.QUEUED:
                queued_count += 1
        if queued_count > self.max_queue_size:
            return _queue_error("Durable queue queued-task count exceeds capacity.")

        self.tasks = hydrated
        self.task_callbacks = {
            task_id: callbacks
            for task_id, callbacks in self.task_callbacks.items()
            if task_id in hydrated
        }
        self.priority_queues = {
            priority: PriorityQueue(maxsize=self.max_queue_size)
            for priority in TaskPriority
        }
        self._queued_count = 0
        for task in hydrated.values():
            if task.status == TaskStatus.QUEUED:
                self.priority_queues[task.priority].put(
                    (task.priority.value, task.created_at, task)
                )
                self._queued_count += 1
        return Result.ok(None)

    def _task_record(self, task: Task) -> Result[Dict[str, Any], str]:
        if not _valid_text(task.task_id, max_length=_MAX_DURABLE_TASK_ID_LENGTH):
            return _queue_error("Durable queue task ID is invalid.")
        if not _valid_text(task.task_type, max_length=_MAX_DURABLE_TEXT_LENGTH):
            return _queue_error("Durable queue task type is invalid.")
        if not isinstance(task.payload, dict) or not isinstance(task.metadata, dict):
            return _queue_error("Durable queue payload and metadata must be objects.")
        for value in (task.payload, task.metadata, task.result):
            if _validate_json_value(value) is not None:
                return _queue_error("Durable queue task JSON is invalid.")
        if (
            not isinstance(task.requirements, list)
            or len(task.requirements) > _MAX_DURABLE_REQUIREMENTS
            or not all(
                _valid_text(item, max_length=_MAX_DURABLE_TEXT_LENGTH)
                for item in task.requirements
            )
        ):
            return _queue_error("Durable queue task requirements are invalid.")
        if task.assigned_agent is not None and not _valid_text(
            task.assigned_agent, max_length=_MAX_DURABLE_TEXT_LENGTH
        ):
            return _queue_error("Durable queue task owner is invalid.")
        if (
            not isinstance(task.timeout_seconds, int)
            or isinstance(task.timeout_seconds, bool)
            or not 0 <= task.timeout_seconds <= _MAX_DURABLE_TIMEOUT_SECONDS
            or not isinstance(task.max_retries, int)
            or isinstance(task.max_retries, bool)
            or not 0 <= task.max_retries <= _MAX_DURABLE_RETRIES
            or not isinstance(task.retry_count, int)
            or isinstance(task.retry_count, bool)
            or not 0 <= task.retry_count <= task.max_retries
        ):
            return _queue_error("Durable queue task retry settings are invalid.")
        if task.error is not None and (
            not isinstance(task.error, str)
            or not task.error
            or len(task.error.encode("utf-8")) > _MAX_TASK_ERROR_BYTES
            or any(ord(char) < 32 and char not in "\r\n\t" for char in task.error)
        ):
            return _queue_error("Durable queue task error is invalid.")
        if (
            not _valid_timestamp(task.created_at, optional=False)
            or not _valid_timestamp(task.started_at)
            or not _valid_timestamp(task.completed_at)
        ):
            return _queue_error("Durable queue task timestamp is invalid.")
        record: Dict[str, Any] = {
            "task_id": task.task_id,
            "task_type": task.task_type,
            "payload": task.payload,
            "priority": task.priority.value,
            "requirements": task.requirements,
            "timeout_seconds": task.timeout_seconds,
            "max_retries": task.max_retries,
            "metadata": task.metadata,
            "status": task.status.value,
            "assigned_agent": task.assigned_agent,
            "created_at": task.created_at,
            "started_at": task.started_at,
            "completed_at": task.completed_at,
            "retry_count": task.retry_count,
            "result": task.result,
            "error": task.error,
            "heartbeat_at": task.heartbeat_at,
        }
        try:
            if not isinstance(task.priority, TaskPriority) or not isinstance(
                task.status, TaskStatus
            ):
                return _queue_error("Durable queue task enum is invalid.")
            encoded = json.dumps(
                record, ensure_ascii=False, allow_nan=False, separators=(",", ":")
            ).encode("utf-8")
        except (TypeError, ValueError, OverflowError, RecursionError):
            return _queue_error("Durable queue task is not JSON serializable.")
        if len(encoded) > self.max_task_bytes:
            return _queue_error("Durable queue task exceeds the byte limit.")
        copied = _copy_json(record)
        if copied.is_err() or not isinstance(copied.unwrap(), dict):
            return _queue_error("Durable queue task JSON is invalid.")
        return Result.ok(copied.unwrap())

    def _state(self) -> Result[Dict[str, Any], str]:
        records: List[Dict[str, Any]] = []
        for task in sorted(
            self.tasks.values(), key=lambda item: (item.created_at, item.task_id)
        ):
            task_result = self._task_record(task)
            if task_result.is_err():
                return Result.err(task_result.unwrap_err())
            records.append(task_result.unwrap())
        state: Dict[str, Any] = {"version": _STATE_VERSION, "tasks": records}
        try:
            encoded = json.dumps(
                state, ensure_ascii=False, allow_nan=False, separators=(",", ":")
            ).encode("utf-8")
        except (TypeError, ValueError, OverflowError, RecursionError):
            return _queue_error("Durable queue state is not JSON serializable.")
        if len(records) > self.max_tasks or len(encoded) > self.max_state_bytes:
            return _queue_error("Durable queue state exceeds the configured limit.")
        return Result.ok(state)

    def _persist(self, state: Mapping[str, Any]) -> Result[None, str]:
        try:
            encoded = json.dumps(
                state, ensure_ascii=False, allow_nan=False, separators=(",", ":")
            ).encode("utf-8")
            if len(encoded) > self.max_state_bytes:
                return _queue_error("Durable queue state exceeds the byte limit.")
            temporary_path: Optional[Path] = None
            try:
                with tempfile.NamedTemporaryFile(
                    mode="wb",
                    dir=str(self.path.parent),
                    prefix=".maple-task-queue-",
                    suffix=".tmp-" + uuid.uuid4().hex,
                    delete=False,
                ) as handle:
                    temporary_path = Path(handle.name)
                    handle.write(encoded)
                    handle.flush()
                    os.fsync(handle.fileno())
                os.replace(str(temporary_path), str(self.path))
                temporary_path = None
            finally:
                if temporary_path is not None:
                    temporary_path.unlink(missing_ok=True)
        except (OSError, TypeError, ValueError, OverflowError, RecursionError):
            return _queue_error("Durable queue state could not be persisted.")
        return Result.ok(None)

    def _acquire(self) -> Result[Lease, str]:
        lease = self._lease_manager.acquire(
            _DURABLE_LEASE_RESOURCE, self._holder, self.lease_ttl_seconds
        )
        if lease.is_err():
            return _queue_error("Durable queue fence is unavailable.")
        return Result.ok(lease.unwrap())

    def _run_durable(
        self,
        operation: Callable[[], Result[Any, Any]],
        *,
        recover_inflight: bool = False,
    ) -> Result[Any, Any]:
        with self._lock:
            lease_result = self._acquire()
            if lease_result.is_err():
                return Result.err(lease_result.unwrap_err())
            operation_result: Result[Any, Any] = Result.err(
                "Durable queue operation did not complete."
            )
            before_state: Optional[Dict[str, Any]] = None
            try:
                state_result = self._read_state()
                if state_result.is_err():
                    operation_result = Result.err(state_result.unwrap_err())
                else:
                    hydrate_result = self._hydrate(
                        state_result.unwrap(), recover_inflight=recover_inflight
                    )
                    if hydrate_result.is_err():
                        operation_result = Result.err(hydrate_result.unwrap_err())
                    else:
                        before_result = self._state()
                        if before_result.is_err():
                            operation_result = Result.err(before_result.unwrap_err())
                        else:
                            before_state = before_result.unwrap()
                            operation_result = operation()
                            if operation_result.is_ok():
                                after_result = self._state()
                                if after_result.is_err():
                                    self._hydrate(before_result.unwrap())
                                    operation_result = Result.err(
                                        after_result.unwrap_err()
                                    )
                                else:
                                    persisted = self._persist(after_result.unwrap())
                                    if persisted.is_err():
                                        self._hydrate(before_result.unwrap())
                                        operation_result = Result.err(
                                            persisted.unwrap_err()
                                        )
            except (
                AttributeError,
                KeyError,
                OverflowError,
                RecursionError,
                TypeError,
                ValueError,
            ):
                if before_state is not None:
                    self._hydrate(before_state)
                operation_result = Result.err(
                    "Durable queue operation could not be completed."
                )
            release_result = self._lease_manager.release(lease_result.unwrap())
            if release_result.is_err() and operation_result.is_ok():
                return Result.err("Durable queue fence release failed.")
            return operation_result

    def submit_task(
        self,
        task_type: str,
        payload: Dict[str, Any],
        priority: TaskPriority = TaskPriority.NORMAL,
        requirements: Optional[List[str]] = None,
        timeout_seconds: int = 300,
        max_retries: int = 3,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Result[str, str]:
        """Submit and atomically persist one bounded task."""
        return self._run_durable(
            lambda: TaskQueue.submit_task(
                self,
                task_type,
                payload,
                priority,
                requirements,
                timeout_seconds,
                max_retries,
                metadata,
            )
        )

    def get_next_task(
        self,
        agent_capabilities: Optional[List[str]] = None,
        timeout_seconds: Optional[float] = None,
        task_types: Optional[Sequence[str]] = None,
    ) -> Result[Optional[Task], str]:
        """Claim a task, polling between fenced durable queue operations."""
        if timeout_seconds is not None and (
            not isinstance(timeout_seconds, (int, float))
            or isinstance(timeout_seconds, bool)
            or not math.isfinite(float(timeout_seconds))
            or timeout_seconds < 0
        ):
            return Result.err("timeout_seconds must be finite and non-negative")
        deadline = (
            time.monotonic() + float(timeout_seconds)
            if timeout_seconds is not None
            else None
        )
        while True:
            result = self._run_durable(
                lambda: TaskQueue.get_next_task(
                    self,
                    agent_capabilities=agent_capabilities,
                    timeout_seconds=0,
                    task_types=task_types,
                )
            )
            if result.is_err() or result.unwrap() is not None:
                return result
            if timeout_seconds == 0 or not self._running:
                return Result.ok(None)
            if deadline is not None:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    return Result.ok(None)
            else:
                remaining = 0.05
            with self._condition:
                if not self._running:
                    return Result.ok(None)
                self._condition.wait(timeout=min(0.05, remaining))

    def update_task_status(
        self,
        task_id: str,
        status: TaskStatus,
        assigned_agent: Optional[str] = None,
        result: Any = None,
        error: Optional[str] = None,
    ) -> Result[Task, str]:
        """Persist an ordinary queue status transition."""
        return self._run_durable(
            lambda: TaskQueue.update_task_status(
                self, task_id, status, assigned_agent, result, error
            )
        )

    def get_task(self, task_id: str) -> Result[Task, str]:
        return self._run_durable(lambda: TaskQueue.get_task(self, task_id))

    def assign_task(self, task_id: str, assigned_agent: str) -> Result[Task, str]:
        return self._run_durable(
            lambda: TaskQueue.assign_task(self, task_id, assigned_agent)
        )

    def start_task(self, task_id: str, assigned_agent: str) -> Result[Task, str]:
        return self._run_durable(
            lambda: TaskQueue.start_task(self, task_id, assigned_agent)
        )

    def heartbeat_task(self, task_id: str, assigned_agent: str) -> Result[Task, str]:
        return self._run_durable(
            lambda: TaskQueue.heartbeat_task(self, task_id, assigned_agent)
        )

    def complete_task(
        self, task_id: str, assigned_agent: str, result: Any = None
    ) -> Result[Task, str]:
        def complete() -> Result[Task, str]:
            task_result = TaskQueue.get_task(self, task_id)
            if task_result.is_err():
                return Result.err(task_result.unwrap_err())
            task = task_result.unwrap()
            if not assigned_agent:
                return Result.err("Assigned agent cannot be empty")
            if task.assigned_agent != assigned_agent:
                return Result.err(f"Task {task_id} is not assigned to {assigned_agent}")
            if task.status not in (TaskStatus.ASSIGNED, TaskStatus.RUNNING):
                return Result.err(
                    f"Task {task_id} cannot be completed from status "
                    f"{task.status.value}"
                )
            return TaskQueue.update_task_status(
                self, task_id, TaskStatus.COMPLETED, result=result
            )

        return self._run_durable(complete)

    def reassign_task(
        self, task_id: str, current_agent: str, new_agent: str
    ) -> Result[Task, str]:
        return self._run_durable(
            lambda: TaskQueue.reassign_task(self, task_id, current_agent, new_agent)
        )

    def fail_task(
        self, task_id: str, assigned_agent: str, error: str
    ) -> Result[Task, str]:
        def fail() -> Result[Task, str]:
            task_result = TaskQueue.get_task(self, task_id)
            if task_result.is_err():
                return Result.err(task_result.unwrap_err())
            task = task_result.unwrap()
            if not assigned_agent:
                return Result.err("Assigned agent cannot be empty")
            if task.assigned_agent != assigned_agent:
                return Result.err(f"Task {task_id} is not assigned to {assigned_agent}")
            if task.status not in (TaskStatus.ASSIGNED, TaskStatus.RUNNING):
                return Result.err(
                    f"Task {task_id} cannot be failed from status "
                    f"{task.status.value}"
                )
            if (
                not isinstance(error, str)
                or not error
                or len(error.encode("utf-8")) > _MAX_TASK_ERROR_BYTES
            ):
                return Result.err(
                    "Task failure error must be a non-empty string of at most "
                    f"{_MAX_TASK_ERROR_BYTES} bytes"
                )
            return TaskQueue.update_task_status(
                self, task_id, TaskStatus.FAILED, error=error
            )

        return self._run_durable(fail)

    def cancel_task(
        self, task_id: str, assigned_agent: Optional[str] = None
    ) -> Result[Task, str]:
        return self._run_durable(
            lambda: TaskQueue.cancel_task(self, task_id, assigned_agent)
        )

    def requeue_task(
        self, task_id: str, assigned_agent: Optional[str] = None
    ) -> Result[None, str]:
        return self._run_durable(
            lambda: TaskQueue.requeue_task(self, task_id, assigned_agent)
        )

    def get_queue_stats(self) -> QueueStats:
        result: Result[QueueStats, str] = self._run_durable(
            lambda: Result.ok(TaskQueue.get_queue_stats(self))
        )
        if result.is_err():
            raise RuntimeError(result.unwrap_err())
        return cast(QueueStats, result.unwrap())

    def list_tasks(
        self,
        status: Optional[TaskStatus] = None,
        task_type: Optional[str] = None,
        limit: int = 100,
    ) -> List[Task]:
        result: Result[List[Task], str] = self._run_durable(
            lambda: Result.ok(TaskQueue.list_tasks(self, status, task_type, limit))
        )
        if result.is_err():
            raise RuntimeError(result.unwrap_err())
        return cast(List[Task], result.unwrap())

    def add_task_callback(
        self, task_id: str, callback: Callable[[Task], None]
    ) -> Result[None, str]:
        return self._run_durable(
            lambda: TaskQueue.add_task_callback(self, task_id, callback)
        )
