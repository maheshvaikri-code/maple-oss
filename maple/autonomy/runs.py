"""Bounded durable checkpoints for autonomous agent runs."""

from __future__ import annotations

import json
import math
import os
import re
import tempfile
import threading
import time
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Protocol, Tuple, Union

from ..core.result import Result
from ..resources.lease import FileLeaseManager
from .durable_leases import DurableRecordLease
from .sessions import SessionMessage

Error = Dict[str, Any]

DEFAULT_MAX_RUN_BYTES = 1_048_576
DEFAULT_MAX_RUN_MESSAGES = 1_000
DEFAULT_MAX_RUN_TRACE = 500
DEFAULT_MAX_RUN_HISTORY = 100
MAX_RUN_HISTORY = 10_000
MAX_RUN_HISTORY_BYTES = 128 * 1_048_576
MAX_RUN_ID_LENGTH = 128
MAX_RUN_DESCRIPTION_LENGTH = 8_192
_IDENTIFIER = re.compile(r"^[A-Za-z0-9_.:-]{1,128}$")
_STATUSES = {"running", "paused", "completed", "failed"}
_MAX_JSON_DEPTH = 16
_MAX_JSON_ITEMS = 10_000
_RUN_LEASE_TTL_SECONDS = 30.0


def _error(error_type: str, message: str, **details: Any) -> Error:
    error: Error = {"errorType": error_type, "message": message}
    if details:
        error["details"] = details
    return error


def _valid_identifier(value: Any, field_name: str) -> Optional[Error]:
    if not isinstance(value, str) or not _IDENTIFIER.fullmatch(value):
        return _error(
            "RUN_IDENTIFIER_INVALID",
            f"{field_name} must contain 1-128 letters, numbers, '_', '.', ':', or '-'.",
            field=field_name,
        )
    return None


def _validate_pending_request_state(
    status: str,
    pending_approval_id: Optional[str],
    pending_input_id: Optional[str],
) -> None:
    """Reject checkpoint states that cannot be resumed deterministically."""

    if pending_approval_id is not None and pending_input_id is not None:
        raise ValueError(
            "run checkpoint cannot contain both a pending approval and input"
        )
    has_pending_request = (
        pending_approval_id is not None or pending_input_id is not None
    )
    if status == "paused" and not has_pending_request:
        raise ValueError(
            "paused run checkpoint must identify one pending approval or input"
        )
    if status != "paused" and has_pending_request:
        raise ValueError("only paused run checkpoints may contain a pending request")


def _copy_json(
    value: Any,
    *,
    path: str = "$",
    depth: int = 0,
    max_depth: int = _MAX_JSON_DEPTH,
    max_items: int = _MAX_JSON_ITEMS,
) -> Result[Any, Error]:
    """Copy only JSON-compatible data without importing executable objects."""

    if depth > max_depth:
        return Result.err(
            _error(
                "RUN_VALUE_TOO_DEEP",
                "Run checkpoint value is too deeply nested.",
                path=path,
            )
        )
    if value is None or isinstance(value, (bool, int, str)):
        return Result.ok(value)
    if isinstance(value, float):
        if not math.isfinite(value):
            return Result.err(
                _error(
                    "RUN_VALUE_INVALID",
                    "Run checkpoint value must be finite.",
                    path=path,
                )
            )
        return Result.ok(value)
    if isinstance(value, Mapping):
        if len(value) > max_items:
            return Result.err(
                _error(
                    "RUN_VALUE_TOO_LARGE",
                    "Run checkpoint mapping has too many items.",
                    path=path,
                )
            )
        copied: Dict[str, Any] = {}
        for key, item in value.items():
            if not isinstance(key, str):
                return Result.err(
                    _error(
                        "RUN_VALUE_INVALID",
                        "Run checkpoint mapping keys must be strings.",
                        path=path,
                    )
                )
            item_result = _copy_json(
                item,
                path=f"{path}.{key}",
                depth=depth + 1,
                max_depth=max_depth,
                max_items=max_items,
            )
            if item_result.is_err():
                return Result.err(item_result.unwrap_err())
            copied[key] = item_result.unwrap()
        return Result.ok(copied)
    if isinstance(value, (list, tuple)):
        if len(value) > max_items:
            return Result.err(
                _error(
                    "RUN_VALUE_TOO_LARGE",
                    "Run checkpoint list has too many items.",
                    path=path,
                )
            )
        copied_list: List[Any] = []
        for index, item in enumerate(value):
            item_result = _copy_json(
                item,
                path=f"{path}[{index}]",
                depth=depth + 1,
                max_depth=max_depth,
                max_items=max_items,
            )
            if item_result.is_err():
                return Result.err(item_result.unwrap_err())
            copied_list.append(item_result.unwrap())
        return Result.ok(copied_list)
    return Result.err(
        _error(
            "RUN_VALUE_INVALID",
            "Run checkpoint values must be JSON-compatible data.",
            path=path,
            value_type=type(value).__name__,
        )
    )


@dataclass(frozen=True)
class AgentRunCheckpoint:
    """JSON-safe state needed to resume one autonomous reasoning run."""

    run_id: str
    agent_id: str
    description: str
    status: str = "running"
    messages: Tuple[SessionMessage, ...] = ()
    reasoning_steps: Tuple[Dict[str, Any], ...] = ()
    step_count: int = 0
    output_retries_used: int = 0
    pending_approval_id: Optional[str] = None
    pending_input_id: Optional[str] = None
    session_id: Optional[str] = None
    session_version: Optional[int] = None
    token_usage: Dict[str, int] = field(default_factory=dict)
    result: Any = None
    error: Optional[Dict[str, Any]] = None
    version: int = 0
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        """Return the strict persistence representation."""

        return {
            "run_id": self.run_id,
            "agent_id": self.agent_id,
            "description": self.description,
            "status": self.status,
            "messages": [message.to_dict() for message in self.messages],
            "reasoning_steps": [dict(step) for step in self.reasoning_steps],
            "step_count": self.step_count,
            "output_retries_used": self.output_retries_used,
            "pending_approval_id": self.pending_approval_id,
            "pending_input_id": self.pending_input_id,
            "session_id": self.session_id,
            "session_version": self.session_version,
            "token_usage": dict(self.token_usage),
            "result": self.result,
            "error": dict(self.error) if self.error is not None else None,
            "version": self.version,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "AgentRunCheckpoint":
        """Parse persisted state without deserializing executable objects."""

        if not isinstance(data, Mapping):
            raise ValueError("run checkpoint must be an object")
        required = (
            "run_id",
            "agent_id",
            "description",
            "status",
            "messages",
            "reasoning_steps",
            "step_count",
            "output_retries_used",
            "pending_approval_id",
            "session_id",
            "session_version",
            "token_usage",
            "result",
            "error",
            "version",
            "created_at",
            "updated_at",
        )
        if any(field_name not in data for field_name in required):
            raise ValueError("run checkpoint is missing a required field")

        for field_name in ("run_id", "agent_id"):
            if _valid_identifier(data.get(field_name), field_name):
                raise ValueError(f"invalid {field_name}")
        description = data["description"]
        if (
            not isinstance(description, str)
            or not description
            or len(description) > MAX_RUN_DESCRIPTION_LENGTH
        ):
            raise ValueError("invalid run description")
        status = data["status"]
        if status not in _STATUSES:
            raise ValueError("invalid run status")

        raw_messages = data["messages"]
        if (
            not isinstance(raw_messages, list)
            or len(raw_messages) > DEFAULT_MAX_RUN_MESSAGES
        ):
            raise ValueError("invalid run messages")
        messages = tuple(SessionMessage.from_dict(item) for item in raw_messages)

        raw_steps = data["reasoning_steps"]
        if not isinstance(raw_steps, list) or len(raw_steps) > DEFAULT_MAX_RUN_TRACE:
            raise ValueError("invalid run reasoning steps")
        steps: List[Dict[str, Any]] = []
        for item in raw_steps:
            if not isinstance(item, Mapping):
                raise ValueError("run reasoning steps must be objects")
            copied = _copy_json(dict(item), path="$.reasoning_steps").unwrap_or(None)
            if not isinstance(copied, dict):
                raise ValueError("invalid run reasoning step")
            steps.append(copied)

        for field_name in ("step_count", "output_retries_used", "version"):
            value = data[field_name]
            if not isinstance(value, int) or isinstance(value, bool) or value < 0:
                raise ValueError(f"invalid {field_name}")
        if data["step_count"] > DEFAULT_MAX_RUN_TRACE:
            raise ValueError("run step count exceeds the configured limit")

        pending_approval_id = data["pending_approval_id"]
        if pending_approval_id is not None and _valid_identifier(
            pending_approval_id, "pending_approval_id"
        ):
            raise ValueError("invalid pending approval ID")
        pending_input_id = data.get("pending_input_id")
        if pending_input_id is not None and _valid_identifier(
            pending_input_id, "pending_input_id"
        ):
            raise ValueError("invalid pending input ID")
        _validate_pending_request_state(status, pending_approval_id, pending_input_id)
        session_id = data["session_id"]
        if session_id is not None and _valid_identifier(session_id, "session_id"):
            raise ValueError("invalid session ID")
        session_version = data["session_version"]
        if session_version is not None and (
            not isinstance(session_version, int)
            or isinstance(session_version, bool)
            or session_version < 0
        ):
            raise ValueError("invalid session version")

        raw_usage = data["token_usage"]
        if not isinstance(raw_usage, Mapping):
            raise ValueError("run token usage must be an object")
        token_usage: Dict[str, int] = {}
        for field_name in ("prompt_tokens", "completion_tokens", "total_tokens"):
            value = raw_usage.get(field_name, 0)
            if not isinstance(value, int) or isinstance(value, bool) or value < 0:
                raise ValueError("invalid run token usage")
            token_usage[field_name] = value

        copied_result = _copy_json(data["result"], path="$.result")
        if copied_result.is_err():
            raise ValueError(copied_result.unwrap_err()["message"])
        raw_error = data["error"]
        copied_error: Optional[Dict[str, Any]] = None
        if raw_error is not None:
            if not isinstance(raw_error, Mapping):
                raise ValueError("run error must be an object or null")
            error_result = _copy_json(dict(raw_error), path="$.error")
            if error_result.is_err() or not isinstance(error_result.unwrap(), dict):
                raise ValueError("invalid run error")
            copied_error = error_result.unwrap()

        created_at = float(data["created_at"])
        updated_at = float(data["updated_at"])
        if not math.isfinite(created_at) or not math.isfinite(updated_at):
            raise ValueError("run timestamps must be finite")
        return cls(
            run_id=data["run_id"],
            agent_id=data["agent_id"],
            description=description,
            status=status,
            messages=messages,
            reasoning_steps=tuple(steps),
            step_count=data["step_count"],
            output_retries_used=data["output_retries_used"],
            pending_approval_id=pending_approval_id,
            pending_input_id=pending_input_id,
            session_id=session_id,
            session_version=session_version,
            token_usage=token_usage,
            result=copied_result.unwrap(),
            error=copied_error,
            version=data["version"],
            created_at=created_at,
            updated_at=updated_at,
        )


class AgentRunStore(Protocol):
    """Persistence contract for bounded autonomous run checkpoints."""

    def load(self, run_id: str) -> Result[Optional[AgentRunCheckpoint], Error]: ...

    def save(
        self,
        checkpoint: AgentRunCheckpoint,
        expected_version: Optional[int] = None,
    ) -> Result[AgentRunCheckpoint, Error]: ...


class AgentRunHistoryStore(AgentRunStore, Protocol):
    """Optional inspection contract for stores retaining run versions."""

    def history(
        self, run_id: str, *, limit: Optional[int] = None
    ) -> Result[List[AgentRunCheckpoint], Error]: ...


def _validate_history_limit(
    run_id: str, max_history: int, limit: Optional[int]
) -> Result[int, Error]:
    identifier_error = _valid_identifier(run_id, "run_id")
    if identifier_error:
        return Result.err(identifier_error)
    effective_limit = max_history if limit is None else limit
    if (
        not isinstance(effective_limit, int)
        or isinstance(effective_limit, bool)
        or not 0 < effective_limit <= max_history
    ):
        return Result.err(
            _error(
                "RUN_HISTORY_LIMIT_INVALID",
                "Run history limit is outside the configured range.",
                max_history=max_history,
            )
        )
    return Result.ok(effective_limit)


def _copy_history(
    snapshots: List[AgentRunCheckpoint], limit: int
) -> List[AgentRunCheckpoint]:
    return [AgentRunCheckpoint.from_dict(item.to_dict()) for item in snapshots[-limit:]]


def _normalize_checkpoint(
    checkpoint: AgentRunCheckpoint, max_bytes: int
) -> Result[AgentRunCheckpoint, Error]:
    try:
        candidate = AgentRunCheckpoint.from_dict(checkpoint.to_dict())
        payload = json.dumps(candidate.to_dict(), ensure_ascii=False, allow_nan=False)
    except (TypeError, ValueError, json.JSONDecodeError) as exc:
        return Result.err(
            _error(
                "RUN_CHECKPOINT_INVALID",
                "Agent run checkpoint is invalid or not JSON serializable.",
                reason=str(exc)[:256],
            )
        )
    if len(payload.encode("utf-8")) > max_bytes:
        return Result.err(
            _error(
                "RUN_CHECKPOINT_SIZE_EXCEEDED",
                "Agent run checkpoint exceeds the configured byte limit.",
                max_checkpoint_bytes=max_bytes,
            )
        )
    return Result.ok(candidate)


class InMemoryAgentRunStore:
    """Thread-safe bounded store for tests and short-lived local hosts.

    The optional history is process-local and inspection-only. It is not a
    replay log and is not retained after the store instance is discarded.
    """

    def __init__(
        self,
        *,
        max_checkpoint_bytes: int = DEFAULT_MAX_RUN_BYTES,
        max_history: int = DEFAULT_MAX_RUN_HISTORY,
    ) -> None:
        if max_checkpoint_bytes <= 0:
            raise ValueError("max_checkpoint_bytes must be positive")
        if (
            not isinstance(max_history, int)
            or isinstance(max_history, bool)
            or not 0 < max_history <= MAX_RUN_HISTORY
        ):
            raise ValueError(f"max_history must be between 1 and {MAX_RUN_HISTORY}")
        self.max_checkpoint_bytes = max_checkpoint_bytes
        self.max_history = max_history
        self._checkpoints: Dict[str, AgentRunCheckpoint] = {}
        self._history: Dict[str, List[AgentRunCheckpoint]] = {}
        self._lock = threading.RLock()

    def load(self, run_id: str) -> Result[Optional[AgentRunCheckpoint], Error]:
        identifier_error = _valid_identifier(run_id, "run_id")
        if identifier_error:
            return Result.err(identifier_error)
        with self._lock:
            checkpoint = self._checkpoints.get(run_id)
            if checkpoint is None:
                return Result.ok(None)
            return Result.ok(AgentRunCheckpoint.from_dict(checkpoint.to_dict()))

    def save(
        self,
        checkpoint: AgentRunCheckpoint,
        expected_version: Optional[int] = None,
    ) -> Result[AgentRunCheckpoint, Error]:
        normalized = _normalize_checkpoint(checkpoint, self.max_checkpoint_bytes)
        if normalized.is_err():
            return Result.err(normalized.unwrap_err())
        candidate = normalized.unwrap()
        with self._lock:
            existing = self._checkpoints.get(candidate.run_id)
            if existing is None:
                if expected_version is not None:
                    return Result.err(
                        _error(
                            "RUN_CHECKPOINT_CONFLICT", "Run checkpoint does not exist."
                        )
                    )
                version = 1
                created_at = candidate.created_at
            else:
                if expected_version != existing.version:
                    return Result.err(
                        _error(
                            "RUN_CHECKPOINT_CONFLICT",
                            "Run checkpoint version does not match.",
                            run_id=candidate.run_id,
                            expected_version=expected_version,
                            actual_version=existing.version,
                        )
                    )
                version = existing.version + 1
                created_at = existing.created_at
            saved = replace(
                candidate,
                version=version,
                created_at=created_at,
                updated_at=time.time(),
            )
            checked = _normalize_checkpoint(saved, self.max_checkpoint_bytes)
            if checked.is_err():
                return Result.err(checked.unwrap_err())
            saved_checkpoint = checked.unwrap()
            self._checkpoints[candidate.run_id] = saved_checkpoint
            snapshots = self._history.setdefault(candidate.run_id, [])
            snapshots.append(AgentRunCheckpoint.from_dict(saved_checkpoint.to_dict()))
            if len(snapshots) > self.max_history:
                del snapshots[: len(snapshots) - self.max_history]
            return Result.ok(AgentRunCheckpoint.from_dict(saved_checkpoint.to_dict()))

    def history(
        self, run_id: str, *, limit: Optional[int] = None
    ) -> Result[List[AgentRunCheckpoint], Error]:
        validated = _validate_history_limit(run_id, self.max_history, limit)
        if validated.is_err():
            return Result.err(validated.unwrap_err())
        with self._lock:
            snapshots = self._history.get(run_id, [])
            if snapshots:
                return Result.ok(_copy_history(snapshots, validated.unwrap()))
            checkpoint = self._checkpoints.get(run_id)
            if checkpoint is None:
                return Result.ok([])
            return Result.ok([AgentRunCheckpoint.from_dict(checkpoint.to_dict())])


class FileAgentRunStore:
    """Atomic JSON store for local process-restart agent recovery.

    The store is thread-safe within one process and fences each run's
    load/compare-and-set save operation across local processes. Exactly-once
    external effects and host notifications remain host responsibilities.
    Successful saves also retain a bounded, version-ordered inspection history
    in ``.history``. History is local durable data, not executable replay.
    """

    def __init__(
        self,
        directory: Union[str, Path],
        *,
        max_checkpoint_bytes: int = DEFAULT_MAX_RUN_BYTES,
        max_history: int = DEFAULT_MAX_RUN_HISTORY,
        lease_manager: Optional[FileLeaseManager] = None,
        lease_ttl_seconds: float = _RUN_LEASE_TTL_SECONDS,
    ) -> None:
        if max_checkpoint_bytes <= 0:
            raise ValueError("max_checkpoint_bytes must be positive")
        if (
            not isinstance(max_history, int)
            or isinstance(max_history, bool)
            or not 0 < max_history <= MAX_RUN_HISTORY
        ):
            raise ValueError(f"max_history must be between 1 and {MAX_RUN_HISTORY}")
        self.directory = Path(directory).expanduser().resolve()
        self.directory.mkdir(parents=True, exist_ok=True)
        self.max_checkpoint_bytes = max_checkpoint_bytes
        self.max_history = max_history
        self.history_directory = (self.directory / ".history").resolve()
        self.history_directory.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._record_leases = DurableRecordLease(
            self.directory,
            namespace="run",
            holder_label="run",
            lease_manager=lease_manager,
            lease_ttl_seconds=lease_ttl_seconds,
        )

    def _path(self, run_id: str) -> Path:
        identifier_error = _valid_identifier(run_id, "run_id")
        if identifier_error:
            raise ValueError(identifier_error["message"])
        path = (self.directory / f"{run_id}.json").resolve()
        if self.directory not in path.parents:
            raise ValueError("run checkpoint path escapes the configured directory")
        return path

    def _read_unlocked(self, run_id: str) -> Optional[AgentRunCheckpoint]:
        path = self._path(run_id)
        if not path.exists():
            return None
        if path.stat().st_size > self.max_checkpoint_bytes:
            raise ValueError("run checkpoint exceeds configured size limit")
        with path.open("r", encoding="utf-8") as handle:
            return AgentRunCheckpoint.from_dict(json.load(handle))

    def _history_path(self, run_id: str) -> Path:
        identifier_error = _valid_identifier(run_id, "run_id")
        if identifier_error:
            raise ValueError(identifier_error["message"])
        path = (self.history_directory / f"{run_id}.json").resolve()
        if self.history_directory not in path.parents:
            raise ValueError("run history path escapes the configured directory")
        return path

    def _read_history_unlocked(self, run_id: str) -> List[AgentRunCheckpoint]:
        path = self._history_path(run_id)
        if not path.exists():
            return []
        if path.stat().st_size > MAX_RUN_HISTORY_BYTES:
            raise ValueError("run history exceeds configured size limit")
        with path.open("r", encoding="utf-8") as handle:
            raw_history = json.load(handle)
        if not isinstance(raw_history, list) or len(raw_history) > MAX_RUN_HISTORY:
            raise ValueError("invalid run history")
        snapshots = [AgentRunCheckpoint.from_dict(item) for item in raw_history]
        previous_version = -1
        for snapshot in snapshots:
            if snapshot.run_id != run_id or snapshot.version <= previous_version:
                raise ValueError("run history versions are not ordered")
            previous_version = snapshot.version
        return snapshots[-self.max_history :]

    def _write_history_unlocked(
        self, run_id: str, snapshots: List[AgentRunCheckpoint]
    ) -> None:
        path = self._history_path(run_id)
        payload = json.dumps(
            [snapshot.to_dict() for snapshot in snapshots],
            ensure_ascii=False,
            allow_nan=False,
            indent=2,
        )
        max_history_bytes = min(
            MAX_RUN_HISTORY_BYTES,
            self.max_checkpoint_bytes * self.max_history + 4_096,
        )
        if len(payload.encode("utf-8")) > max_history_bytes:
            raise ValueError("run history exceeds configured size limit")
        temporary_path: Optional[Path] = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                dir=str(self.history_directory),
                prefix=f".{run_id}.",
                suffix=".tmp",
                delete=False,
            ) as handle:
                temporary_path = Path(handle.name)
                handle.write(payload)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(str(temporary_path), str(path))
            temporary_path = None
        finally:
            if temporary_path is not None:
                try:
                    temporary_path.unlink()
                except OSError:
                    pass

    def _with_run_lease(
        self,
        run_id: str,
        operation: str,
        callback: Any,
    ) -> Result[Any, Error]:
        identifier_error = _valid_identifier(run_id, "run_id")
        if identifier_error:
            return Result.err(identifier_error)
        return self._record_leases.run(
            run_id,
            operation,
            callback,
            acquire_error_type="RUN_CHECKPOINT_LEASE_ERROR",
            acquire_error_message="Agent run checkpoint lease is unavailable.",
            release_error_type="RUN_CHECKPOINT_LEASE_RELEASE_ERROR",
            release_error_message=(
                "Agent run checkpoint lease could not be released safely."
            ),
        )

    def _load_without_lease(
        self, run_id: str
    ) -> Result[Optional[AgentRunCheckpoint], Error]:
        try:
            with self._lock:
                checkpoint = self._read_unlocked(run_id)
                return Result.ok(
                    None
                    if checkpoint is None
                    else AgentRunCheckpoint.from_dict(checkpoint.to_dict())
                )
        except (OSError, TypeError, ValueError, json.JSONDecodeError) as exc:
            return Result.err(
                _error(
                    "RUN_CHECKPOINT_LOAD_ERROR",
                    "Failed to load agent run checkpoint.",
                    reason=str(exc)[:256],
                )
            )

    def load(self, run_id: str) -> Result[Optional[AgentRunCheckpoint], Error]:
        return self._with_run_lease(
            run_id,
            "load",
            lambda: self._load_without_lease(run_id),
        )

    def _save_without_lease(
        self,
        candidate: AgentRunCheckpoint,
        expected_version: Optional[int] = None,
    ) -> Result[AgentRunCheckpoint, Error]:
        temporary_path: Optional[Path] = None
        try:
            with self._lock:
                existing = self._read_unlocked(candidate.run_id)
                try:
                    history = self._read_history_unlocked(candidate.run_id)
                except (OSError, TypeError, ValueError, json.JSONDecodeError) as exc:
                    return Result.err(
                        _error(
                            "RUN_HISTORY_LOAD_ERROR",
                            "Failed to load agent run checkpoint history.",
                            reason=str(exc)[:256],
                        )
                    )
                if existing is None and history:
                    return Result.err(
                        _error(
                            "RUN_HISTORY_LOAD_ERROR",
                            "Run checkpoint history exists without its current checkpoint.",
                        )
                    )
                if existing is not None and history:
                    latest_history = history[-1]
                    if latest_history.version > existing.version:
                        return Result.err(
                            _error(
                                "RUN_HISTORY_LOAD_ERROR",
                                "Run checkpoint history is ahead of its current checkpoint.",
                            )
                        )
                    if latest_history.version == existing.version and (
                        latest_history.to_dict() != existing.to_dict()
                    ):
                        return Result.err(
                            _error(
                                "RUN_HISTORY_LOAD_ERROR",
                                "Run checkpoint history disagrees with its current checkpoint.",
                            )
                        )
                    if latest_history.version < existing.version:
                        history.append(AgentRunCheckpoint.from_dict(existing.to_dict()))
                if existing is None:
                    if expected_version is not None:
                        return Result.err(
                            _error(
                                "RUN_CHECKPOINT_CONFLICT",
                                "Run checkpoint does not exist.",
                            )
                        )
                    version = 1
                    created_at = candidate.created_at
                else:
                    if expected_version != existing.version:
                        return Result.err(
                            _error(
                                "RUN_CHECKPOINT_CONFLICT",
                                "Run checkpoint version does not match.",
                                run_id=candidate.run_id,
                                expected_version=expected_version,
                                actual_version=existing.version,
                            )
                        )
                    version = existing.version + 1
                    created_at = existing.created_at
                saved = replace(
                    candidate,
                    version=version,
                    created_at=created_at,
                    updated_at=time.time(),
                )
                checked = _normalize_checkpoint(saved, self.max_checkpoint_bytes)
                if checked.is_err():
                    return Result.err(checked.unwrap_err())
                payload = json.dumps(
                    checked.unwrap().to_dict(),
                    ensure_ascii=False,
                    allow_nan=False,
                    indent=2,
                )
                with tempfile.NamedTemporaryFile(
                    mode="w",
                    encoding="utf-8",
                    dir=str(self.directory),
                    prefix=f".{candidate.run_id}.",
                    suffix=".tmp",
                    delete=False,
                ) as handle:
                    temporary_path = Path(handle.name)
                    handle.write(payload)
                    handle.flush()
                    os.fsync(handle.fileno())
                os.replace(str(temporary_path), str(self._path(candidate.run_id)))
                temporary_path = None
                saved_checkpoint = checked.unwrap()
                history.append(AgentRunCheckpoint.from_dict(saved_checkpoint.to_dict()))
                if len(history) > self.max_history:
                    del history[: len(history) - self.max_history]
                try:
                    self._write_history_unlocked(candidate.run_id, history)
                except (OSError, TypeError, ValueError, json.JSONDecodeError) as exc:
                    return Result.err(
                        _error(
                            "RUN_HISTORY_SAVE_ERROR",
                            "Failed to save agent run checkpoint history.",
                            reason=str(exc)[:256],
                        )
                    )
                return Result.ok(
                    AgentRunCheckpoint.from_dict(saved_checkpoint.to_dict())
                )
        except (OSError, TypeError, ValueError, json.JSONDecodeError) as exc:
            return Result.err(
                _error(
                    "RUN_CHECKPOINT_SAVE_ERROR",
                    "Failed to save agent run checkpoint.",
                    reason=str(exc)[:256],
                )
            )
        finally:
            if temporary_path is not None:
                try:
                    temporary_path.unlink()
                except OSError:
                    pass

    def save(
        self,
        checkpoint: AgentRunCheckpoint,
        expected_version: Optional[int] = None,
    ) -> Result[AgentRunCheckpoint, Error]:
        normalized = _normalize_checkpoint(checkpoint, self.max_checkpoint_bytes)
        if normalized.is_err():
            return Result.err(normalized.unwrap_err())
        candidate = normalized.unwrap()
        return self._with_run_lease(
            candidate.run_id,
            "save",
            lambda: self._save_without_lease(candidate, expected_version),
        )

    def _history_without_lease(
        self, run_id: str, limit: int
    ) -> Result[List[AgentRunCheckpoint], Error]:
        try:
            with self._lock:
                snapshots = self._read_history_unlocked(run_id)
                if snapshots:
                    return Result.ok(_copy_history(snapshots, limit))
                checkpoint = self._read_unlocked(run_id)
                if checkpoint is None:
                    return Result.ok([])
                return Result.ok([AgentRunCheckpoint.from_dict(checkpoint.to_dict())])
        except (OSError, TypeError, ValueError, json.JSONDecodeError) as exc:
            return Result.err(
                _error(
                    "RUN_HISTORY_LOAD_ERROR",
                    "Failed to load agent run checkpoint history.",
                    reason=str(exc)[:256],
                )
            )

    def history(
        self, run_id: str, *, limit: Optional[int] = None
    ) -> Result[List[AgentRunCheckpoint], Error]:
        validated = _validate_history_limit(run_id, self.max_history, limit)
        if validated.is_err():
            return Result.err(validated.unwrap_err())
        return self._with_run_lease(
            run_id,
            "history",
            lambda: self._history_without_lease(run_id, validated.unwrap()),
        )
