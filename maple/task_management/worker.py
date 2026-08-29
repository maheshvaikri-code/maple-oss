"""Trusted local execution of tasks from a MAPLE task queue."""

from __future__ import annotations

import math
import threading
from dataclasses import replace
from typing import Any, Callable, Dict, Iterable, Mapping, Optional

from ..autonomy.execution import (
    CancellationToken,
    ExecutionPolicy,
    TrustedLocalExecutor,
)
from ..core.result import Result
from .task_queue import Task, TaskQueue

TaskHandler = Callable[[Mapping[str, Any]], Any]

_MAX_WORKER_ID_BYTES = 128
_MAX_HANDLER_TYPES = 256
_MAX_TASK_TYPE_BYTES = 256
_MAX_CAPABILITIES = 128
_MAX_CAPABILITY_BYTES = 128
_MAX_POLL_TIMEOUT_SECONDS = 60.0
_MAX_TASK_TIMEOUT_SECONDS = 7 * 24 * 60 * 60
_MAX_TASK_ERROR_BYTES = 8_192
_SAFE_FAILURE_TYPES = frozenset(
    {
        "EXECUTION_APPROVAL_DENIED",
        "EXECUTION_APPROVAL_ERROR",
        "EXECUTION_APPROVAL_REQUIRED",
        "EXECUTION_CANCELLED",
        "EXECUTION_CAPACITY_EXCEEDED",
        "EXECUTION_CONFIG_INVALID",
        "EXECUTION_ERROR",
        "EXECUTION_INPUT_INVALID",
        "EXECUTION_INPUT_TOO_LARGE",
        "EXECUTION_NON_JSON_VALUE",
        "EXECUTION_OUTPUT_TOO_LARGE",
        "EXECUTION_TIMEOUT",
        "TASK_HANDLER_ERROR",
    }
)


def _bounded_text(value: Any, *, maximum_bytes: int) -> bool:
    if (
        not isinstance(value, str)
        or not value
        or "\x00" in value
        or any(ord(character) < 32 or ord(character) == 127 for character in value)
    ):
        return False
    try:
        return len(value.encode("utf-8")) <= maximum_bytes
    except UnicodeEncodeError:
        return False


def _bounded_failure(error: Any, default_type: str = "TASK_HANDLER_ERROR") -> str:
    """Convert an execution error into a bounded, non-secret task message."""
    error_type = (
        default_type if default_type in _SAFE_FAILURE_TYPES else "TASK_HANDLER_ERROR"
    )
    if isinstance(error, Mapping):
        try:
            candidate = error.get("errorType")
        except Exception:
            candidate = None
        if candidate in _SAFE_FAILURE_TYPES:
            error_type = candidate
    message = f"Task execution failed with {error_type}."
    encoded = message.encode("utf-8")[:_MAX_TASK_ERROR_BYTES]
    return encoded.decode("utf-8", errors="ignore") or "Task execution failed."


class TrustedTaskWorker:
    """Run one queued task through explicitly trusted local handlers.

    The worker is not a sandbox. Handlers execute in the local process through
    ``TrustedLocalExecutor`` and must be trusted by the host. Callers own any
    polling loop or thread; one invocation of :meth:`run_once` handles at most
    one task.
    """

    def __init__(
        self,
        task_queue: TaskQueue,
        worker_id: str,
        handlers: Mapping[str, TaskHandler],
        *,
        capabilities: Optional[Iterable[str]] = None,
        execution_policy: Optional[ExecutionPolicy] = None,
        max_task_timeout_seconds: int = _MAX_TASK_TIMEOUT_SECONDS,
        approval_callback: Optional[Callable[[str], bool]] = None,
    ) -> None:
        if not isinstance(task_queue, TaskQueue):
            raise TypeError("task_queue must be a TaskQueue")
        if not _bounded_text(worker_id, maximum_bytes=_MAX_WORKER_ID_BYTES):
            raise ValueError("worker_id must be a non-empty bounded string")
        if not isinstance(handlers, Mapping):
            raise TypeError("handlers must be a mapping of task types to callables")
        if len(handlers) > _MAX_HANDLER_TYPES:
            raise ValueError("handlers exceeds the maximum number of task types")

        normalized_handlers: Dict[str, TaskHandler] = {}
        for task_type, handler in handlers.items():
            if not _bounded_text(task_type, maximum_bytes=_MAX_TASK_TYPE_BYTES):
                raise ValueError("handler task types must be non-empty bounded strings")
            if not callable(handler):
                raise TypeError(f"handler for {task_type!r} must be callable")
            normalized_handlers[task_type] = handler

        if isinstance(capabilities, str):
            raise TypeError("capabilities must be an iterable of labels")
        normalized_capabilities = []
        try:
            for index, capability in enumerate(capabilities or ()):
                if index >= _MAX_CAPABILITIES:
                    raise ValueError(
                        "capabilities exceeds the maximum number of entries"
                    )
                normalized_capabilities.append(capability)
        except TypeError as exc:
            raise TypeError("capabilities must be an iterable of labels") from exc
        if any(
            not _bounded_text(capability, maximum_bytes=_MAX_CAPABILITY_BYTES)
            for capability in normalized_capabilities
        ):
            raise ValueError("capabilities must contain non-empty bounded strings")

        policy = execution_policy or ExecutionPolicy()
        policy_error = policy.validate()
        if policy_error is not None:
            raise ValueError(policy_error["message"])
        if (
            not isinstance(max_task_timeout_seconds, int)
            or isinstance(max_task_timeout_seconds, bool)
            or not 1 <= max_task_timeout_seconds <= _MAX_TASK_TIMEOUT_SECONDS
        ):
            raise ValueError(
                "max_task_timeout_seconds must be an integer from 1 to "
                f"{_MAX_TASK_TIMEOUT_SECONDS}"
            )
        if approval_callback is not None and not callable(approval_callback):
            raise TypeError("approval_callback must be callable")

        self.task_queue = task_queue
        self.worker_id = worker_id
        self.handlers = normalized_handlers
        self.capabilities = tuple(dict.fromkeys(normalized_capabilities))
        self.execution_policy = policy
        self.max_task_timeout_seconds = max_task_timeout_seconds
        self.approval_callback = approval_callback
        self._execution_lock = threading.Lock()

    def run_once(
        self,
        *,
        timeout_seconds: float = 0.0,
        cancellation: Optional[CancellationToken] = None,
    ) -> Result[Optional[Task], str]:
        """Claim and execute at most one registered task.

        ``ok(None)`` means no registered task was available during the bounded
        poll. Queue and terminal-transition failures are returned as errors;
        a handler failure is represented by an ``ok`` result containing the
        resulting ``FAILED`` task.
        """
        if (
            not isinstance(timeout_seconds, (int, float))
            or isinstance(timeout_seconds, bool)
            or not math.isfinite(float(timeout_seconds))
            or timeout_seconds < 0
            or timeout_seconds > _MAX_POLL_TIMEOUT_SECONDS
        ):
            return Result.err(
                "timeout_seconds must be finite, non-negative, and at most "
                f"{_MAX_POLL_TIMEOUT_SECONDS:g}"
            )
        if cancellation is not None and cancellation.is_cancelled():
            return Result.err("Task worker cancellation was requested before polling")
        if not self.handlers:
            return Result.ok(None)
        if not self._execution_lock.acquire(blocking=False):
            return Result.err("Task worker is already executing a task")

        try:
            next_result = self.task_queue.get_next_task(
                agent_capabilities=list(self.capabilities),
                timeout_seconds=float(timeout_seconds),
                task_types=tuple(self.handlers),
            )
            if next_result.is_err():
                return Result.err(next_result.unwrap_err())
            task = next_result.unwrap()
            if task is None:
                return Result.ok(None)

            assigned = self.task_queue.assign_task(task.task_id, self.worker_id)
            if assigned.is_err():
                return Result.err(
                    f"Task {task.task_id} could not be claimed: "
                    f"{assigned.unwrap_err()}"
                )

            if cancellation is not None and cancellation.is_cancelled():
                return self._cancel_owned_task(task.task_id)

            preflight_error = self._validate_task(task)
            if preflight_error is not None:
                return self._fail_owned_task(task.task_id, preflight_error)

            handler = self.handlers.get(task.task_type)
            if handler is None:
                return self._fail_owned_task(
                    task.task_id, "No trusted handler is registered for this task."
                )

            try:
                handler_payload = dict(task.payload)
            except Exception:
                return self._fail_owned_task(
                    task.task_id, "Task payload could not be copied."
                )

            started = self.task_queue.start_task(task.task_id, self.worker_id)
            if started.is_err():
                return Result.err(
                    f"Task {task.task_id} could not be started: "
                    f"{started.unwrap_err()}"
                )

            execution_policy = replace(
                self.execution_policy,
                timeout_seconds=min(
                    float(task.timeout_seconds),
                    float(self.execution_policy.timeout_seconds),
                ),
                max_concurrent=1,
            )
            executor = TrustedLocalExecutor(
                execution_policy,
                approval_callback=self.approval_callback,
                thread_name_prefix="maple-task-worker",
            )
            execution = executor.execute(
                task.task_type,
                handler,
                args=(handler_payload,),
                cancellation=cancellation,
            )
            if execution.is_err():
                if (
                    cancellation is not None
                    and cancellation.is_cancelled()
                    and execution.unwrap_err().get("errorType") == "EXECUTION_CANCELLED"
                ):
                    return self._cancel_owned_task(task.task_id)
                return self._fail_owned_task(
                    task.task_id, _bounded_failure(execution.unwrap_err())
                )

            value = execution.unwrap()
            if isinstance(value, Result):
                if value.is_err():
                    return self._fail_owned_task(
                        task.task_id, _bounded_failure(value.unwrap_err())
                    )
                value = value.unwrap()

            completed = self.task_queue.complete_task(
                task.task_id, self.worker_id, result=value
            )
            if completed.is_err():
                return Result.err(
                    f"Task {task.task_id} could not be completed: "
                    f"{completed.unwrap_err()}"
                )
            return Result.ok(completed.unwrap())
        finally:
            self._execution_lock.release()

    def _validate_task(self, task: Task) -> Optional[str]:
        if not isinstance(task.payload, Mapping):
            return "Task payload must be an object."
        timeout = task.timeout_seconds
        if (
            not isinstance(timeout, (int, float))
            or isinstance(timeout, bool)
            or not math.isfinite(float(timeout))
            or timeout <= 0
            or timeout > self.max_task_timeout_seconds
        ):
            return "Task timeout must be finite, positive, and within the worker limit."
        return None

    def _fail_owned_task(self, task_id: str, error: str) -> Result[Optional[Task], str]:
        failed = self.task_queue.fail_task(task_id, self.worker_id, error)
        if failed.is_err():
            return Result.err(
                f"Task {task_id} failure transition failed: {failed.unwrap_err()}"
            )
        return Result.ok(failed.unwrap())

    def _cancel_owned_task(self, task_id: str) -> Result[Optional[Task], str]:
        cancelled = self.task_queue.cancel_task(task_id, self.worker_id)
        if cancelled.is_err():
            return Result.err(
                f"Task {task_id} cancellation transition failed: "
                f"{cancelled.unwrap_err()}"
            )
        return Result.ok(cancelled.unwrap())


__all__ = ["TaskHandler", "TrustedTaskWorker"]
