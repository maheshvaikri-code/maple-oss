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
from .sessions import SessionMessage

Error = Dict[str, Any]

DEFAULT_MAX_RUN_BYTES = 1_048_576
DEFAULT_MAX_RUN_MESSAGES = 1_000
DEFAULT_MAX_RUN_TRACE = 500
MAX_RUN_ID_LENGTH = 128
MAX_RUN_DESCRIPTION_LENGTH = 8_192
_IDENTIFIER = re.compile(r"^[A-Za-z0-9_.:-]{1,128}$")
_STATUSES = {"running", "paused", "completed", "failed"}
_MAX_JSON_DEPTH = 16
_MAX_JSON_ITEMS = 10_000


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
    """Thread-safe bounded store for tests and short-lived local hosts."""

    def __init__(self, *, max_checkpoint_bytes: int = DEFAULT_MAX_RUN_BYTES) -> None:
        if max_checkpoint_bytes <= 0:
            raise ValueError("max_checkpoint_bytes must be positive")
        self.max_checkpoint_bytes = max_checkpoint_bytes
        self._checkpoints: Dict[str, AgentRunCheckpoint] = {}
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
            self._checkpoints[candidate.run_id] = checked.unwrap()
            return Result.ok(AgentRunCheckpoint.from_dict(checked.unwrap().to_dict()))


class FileAgentRunStore:
    """Atomic JSON store for local process-restart agent recovery.

    The store is thread-safe within one process. Cross-process leases and
    exactly-once external effects remain host responsibilities.
    """

    def __init__(
        self,
        directory: Union[str, Path],
        *,
        max_checkpoint_bytes: int = DEFAULT_MAX_RUN_BYTES,
    ) -> None:
        if max_checkpoint_bytes <= 0:
            raise ValueError("max_checkpoint_bytes must be positive")
        self.directory = Path(directory).expanduser().resolve()
        self.directory.mkdir(parents=True, exist_ok=True)
        self.max_checkpoint_bytes = max_checkpoint_bytes
        self._lock = threading.RLock()

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

    def load(self, run_id: str) -> Result[Optional[AgentRunCheckpoint], Error]:
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

    def save(
        self,
        checkpoint: AgentRunCheckpoint,
        expected_version: Optional[int] = None,
    ) -> Result[AgentRunCheckpoint, Error]:
        normalized = _normalize_checkpoint(checkpoint, self.max_checkpoint_bytes)
        if normalized.is_err():
            return Result.err(normalized.unwrap_err())
        candidate = normalized.unwrap()
        temporary_path: Optional[Path] = None
        try:
            with self._lock:
                existing = self._read_unlocked(candidate.run_id)
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
                return Result.ok(
                    AgentRunCheckpoint.from_dict(checked.unwrap().to_dict())
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
