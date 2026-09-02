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
"""Bounded execution primitives for explicitly trusted local handlers.

Lives in ``core`` because both the autonomy layer and task_management
need it. It previously sat in ``autonomy``, which made
``task_management.worker`` import upward into ``autonomy`` and closed a
module-level import cycle (ADR-158). ``maple.autonomy.execution`` remains
as a re-export shim, so every existing import path still works."""

from __future__ import annotations

import json
import math
import threading
import time
from concurrent.futures import CancelledError, ThreadPoolExecutor, TimeoutError
from dataclasses import dataclass
from typing import Any, Callable, Dict, Mapping, Optional, Protocol, Sequence

from .result import Result

Error = Dict[str, Any]
Handler = Callable[..., Any]


class ExecutionExecutor(Protocol):
    """Protocol implemented by an executor that runs a trusted handler."""

    def execute(
        self,
        operation: str,
        handler: Handler,
        *,
        args: Sequence[Any] = (),
        kwargs: Optional[Mapping[str, Any]] = None,
        cancellation: Optional["CancellationToken"] = None,
    ) -> Result[Any, Error]:
        """Execute a handler under the executor's policy."""


@dataclass(frozen=True)
class ExecutionPolicy:
    """Limits for one trusted-local execution."""

    timeout_seconds: float = 30.0
    max_input_bytes: int = 1_048_576
    max_output_bytes: int = 1_048_576
    max_concurrent: int = 4
    require_approval: bool = False

    def validate(self) -> Optional[Error]:
        """Return a structured configuration error, if the policy is invalid."""
        if (
            not isinstance(self.timeout_seconds, (int, float))
            or isinstance(self.timeout_seconds, bool)
            or not math.isfinite(self.timeout_seconds)
            or self.timeout_seconds <= 0
        ):
            return _error(
                "EXECUTION_CONFIG_INVALID",
                "timeout_seconds must be finite and positive.",
            )
        for name, value in (
            ("max_input_bytes", self.max_input_bytes),
            ("max_output_bytes", self.max_output_bytes),
            ("max_concurrent", self.max_concurrent),
        ):
            if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
                return _error(
                    "EXECUTION_CONFIG_INVALID", f"{name} must be a positive integer."
                )
        if not isinstance(self.require_approval, bool):
            return _error(
                "EXECUTION_CONFIG_INVALID", "require_approval must be boolean."
            )
        return None


class CancellationToken:
    """Thread-safe cancellation signal for cooperative handlers."""

    def __init__(self) -> None:
        self._event = threading.Event()

    def cancel(self) -> None:
        """Request cancellation."""
        self._event.set()

    def is_cancelled(self) -> bool:
        """Return whether cancellation has been requested."""
        return self._event.is_set()

    def wait(self, timeout: Optional[float] = None) -> bool:
        """Wait for cancellation and return whether it was signalled."""
        return self._event.wait(timeout)


def _error(error_type: str, message: str, **details: Any) -> Error:
    error: Error = {"errorType": error_type, "message": message}
    if details:
        error["details"] = details
    return error


def _serialized_size(value: Any) -> Result[int, Error]:
    try:
        encoded = json.dumps(
            value,
            ensure_ascii=False,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError, OverflowError):
        return Result.err(
            _error(
                "EXECUTION_NON_JSON_VALUE",
                "Execution values must be JSON serializable.",
            )
        )
    return Result.ok(len(encoded))


class TrustedLocalExecutor:
    """Run trusted Python handlers with cooperative, bounded safeguards.

    This class is not a sandbox and must not be used for model-generated code,
    shell commands, or other untrusted execution. A timeout requests
    cancellation and returns promptly; Python cannot forcibly kill a running
    thread, so handlers with external side effects must cooperate.
    """

    def __init__(
        self,
        policy: Optional[ExecutionPolicy] = None,
        *,
        approval_callback: Optional[Callable[[str], bool]] = None,
        thread_name_prefix: str = "maple-trusted",
    ) -> None:
        self.policy = policy or ExecutionPolicy()
        self.approval_callback = approval_callback
        self.thread_name_prefix = thread_name_prefix
        slot_count = self.policy.max_concurrent
        if (
            not isinstance(slot_count, int)
            or isinstance(slot_count, bool)
            or slot_count <= 0
        ):
            slot_count = 1
        self._slots = threading.BoundedSemaphore(slot_count)

    def execute(
        self,
        operation: str,
        handler: Handler,
        *,
        args: Sequence[Any] = (),
        kwargs: Optional[Mapping[str, Any]] = None,
        cancellation: Optional[CancellationToken] = None,
    ) -> Result[Any, Error]:
        """Execute one trusted handler and return a structured failure on bounds."""
        policy_error = self.policy.validate()
        if policy_error is not None:
            return Result.err(policy_error)
        if not isinstance(operation, str) or not operation or len(operation) > 256:
            return Result.err(
                _error(
                    "EXECUTION_INPUT_INVALID",
                    "operation must be a non-empty bounded string.",
                )
            )
        if not callable(handler):
            return Result.err(
                _error("EXECUTION_INPUT_INVALID", "handler must be callable.")
            )

        token = cancellation or CancellationToken()
        if token.is_cancelled():
            return Result.err(
                _error("EXECUTION_CANCELLED", "Execution was cancelled before start.")
            )
        if self.policy.require_approval:
            if self.approval_callback is None:
                return Result.err(
                    _error(
                        "EXECUTION_APPROVAL_REQUIRED", "Execution approval is required."
                    )
                )
            try:
                approved = self.approval_callback(operation)
            except Exception:
                return Result.err(
                    _error(
                        "EXECUTION_APPROVAL_ERROR", "Execution approval failed closed."
                    )
                )
            if approved is not True:
                return Result.err(
                    _error(
                        "EXECUTION_APPROVAL_DENIED", "Execution approval was denied."
                    )
                )

        call_args = tuple(args)
        call_kwargs = dict(kwargs or {})
        input_size = _serialized_size({"args": call_args, "kwargs": call_kwargs})
        if input_size.is_err():
            return Result.err(input_size.unwrap_err())
        if input_size.unwrap() > self.policy.max_input_bytes:
            return Result.err(
                _error(
                    "EXECUTION_INPUT_TOO_LARGE",
                    "Execution input exceeds the byte limit.",
                )
            )

        if not self._slots.acquire(blocking=False):
            return Result.err(
                _error(
                    "EXECUTION_CAPACITY_EXCEEDED",
                    "Execution concurrency limit reached.",
                )
            )

        worker = ThreadPoolExecutor(
            max_workers=1, thread_name_prefix=self.thread_name_prefix
        )
        future = worker.submit(handler, *call_args, **call_kwargs)
        timed_out = False
        try:
            deadline = time.monotonic() + self.policy.timeout_seconds
            while True:
                if token.is_cancelled():
                    future.cancel()
                    return Result.err(
                        _error("EXECUTION_CANCELLED", "Execution was cancelled.")
                    )
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    timed_out = True
                    token.cancel()
                    future.cancel()
                    return Result.err(
                        _error(
                            "EXECUTION_TIMEOUT",
                            "Execution exceeded its timeout.",
                            operation=operation,
                        )
                    )
                try:
                    value = future.result(timeout=min(remaining, 0.05))
                    break
                except TimeoutError:
                    continue
                except CancelledError:
                    return Result.err(
                        _error("EXECUTION_CANCELLED", "Execution was cancelled.")
                    )
                except Exception as exc:
                    return Result.err(
                        _error(
                            "EXECUTION_ERROR",
                            "Trusted handler raised an exception.",
                            exception=type(exc).__name__,
                        )
                    )

            if token.is_cancelled():
                return Result.err(
                    _error("EXECUTION_CANCELLED", "Execution was cancelled.")
                )
            if isinstance(value, Result):
                measured = value.unwrap() if value.is_ok() else value.unwrap_err()
            else:
                measured = value
            output_size = _serialized_size(measured)
            if output_size.is_err():
                return Result.err(output_size.unwrap_err())
            if output_size.unwrap() > self.policy.max_output_bytes:
                return Result.err(
                    _error(
                        "EXECUTION_OUTPUT_TOO_LARGE",
                        "Execution output exceeds the byte limit.",
                    )
                )
            return Result.ok(value)
        finally:
            if timed_out:
                worker.shutdown(wait=False)
                future.add_done_callback(lambda _: self._slots.release())
            else:
                worker.shutdown(wait=True)
                self._slots.release()
