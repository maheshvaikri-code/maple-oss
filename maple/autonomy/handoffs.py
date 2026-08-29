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
"""Bounded durable identity and ownership records for local handoffs."""

from __future__ import annotations

import json
import math
import os
import re
import tempfile
import threading
import time
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, Callable, Dict, List, Mapping, Optional, Protocol, Union

from ..core.result import Result
from ..resources.lease import FileLeaseManager
from .durable_leases import DurableRecordLease

Error = Dict[str, Any]
_MAX_IDENTIFIER_LENGTH = 256
_MAX_ERROR_TYPE_LENGTH = 128
_MAX_LIST_LIMIT = 100
_MAX_RECORD_BYTES = 262_144
_MAX_RESULT_BYTES = 65_536
_LEASE_TTL_SECONDS = 30.0
_DIGEST_PATTERN = re.compile(r"^[0-9a-f]{64}$")
_STATUSES = frozenset({"pending", "accepted", "completed", "failed"})


def _error(error_type: str, message: str, **details: Any) -> Error:
    value: Error = {"errorType": error_type, "message": message}
    if details:
        value["details"] = details
    return value


def _valid_text(value: Any, *, max_length: int) -> bool:
    return (
        isinstance(value, str)
        and bool(value)
        and len(value) <= max_length
        and not any(ord(char) < 32 for char in value)
    )


def _valid_digest(value: Any) -> bool:
    return isinstance(value, str) and _DIGEST_PATTERN.fullmatch(value) is not None


def _finite_number(value: Any) -> bool:
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        return False
    try:
        return math.isfinite(value)
    except OverflowError:
        return False


def _copy_result(value: Any) -> Optional[Dict[str, Any]]:
    """Copy one bounded JSON object retained on a completed handoff."""
    if value is None:
        return None
    if not isinstance(value, Mapping):
        raise ValueError("handoff result must be an object or null")
    try:
        encoded = json.dumps(
            dict(value), ensure_ascii=False, allow_nan=False, separators=(",", ":")
        )
        encoded_bytes = encoded.encode("utf-8")
        if len(encoded_bytes) > _MAX_RESULT_BYTES:
            raise ValueError("handoff result exceeds the configured byte limit")
        copied = json.loads(encoded)
    except (TypeError, ValueError, OverflowError, RecursionError, UnicodeError) as exc:
        raise ValueError("handoff result must be JSON serializable") from exc
    if not isinstance(copied, dict):
        raise ValueError("handoff result must be an object")
    return copied


@dataclass(frozen=True)
class HandoffRecord:
    """Durable local handoff identity with explicit ownership state."""

    handoff_id: str
    source_agent_id: str
    target_agent_id: str
    task_digest: str
    context_digest: Optional[str] = None
    status: str = "pending"
    owner_id: str = ""
    target_goal_id: Optional[str] = None
    error_type: Optional[str] = None
    created_at: float = 0.0
    updated_at: float = 0.0
    result: Optional[Dict[str, Any]] = None

    @classmethod
    def pending(
        cls,
        handoff_id: str,
        source_agent_id: str,
        target_agent_id: str,
        task_digest: str,
        context_digest: Optional[str] = None,
    ) -> "HandoffRecord":
        now = time.time()
        return cls(
            handoff_id=handoff_id,
            source_agent_id=source_agent_id,
            target_agent_id=target_agent_id,
            task_digest=task_digest,
            context_digest=context_digest,
            owner_id=source_agent_id,
            created_at=now,
            updated_at=now,
        )

    def validate(self) -> Optional[Error]:
        for name, value in (
            ("handoff_id", self.handoff_id),
            ("source_agent_id", self.source_agent_id),
            ("target_agent_id", self.target_agent_id),
            ("owner_id", self.owner_id),
        ):
            if not _valid_text(value, max_length=_MAX_IDENTIFIER_LENGTH):
                return _error(
                    "HANDOFF_RECORD_INVALID",
                    f"{name} must be bounded text.",
                )
        if not _valid_digest(self.task_digest):
            return _error(
                "HANDOFF_RECORD_INVALID", "task_digest must be a SHA-256 digest."
            )
        if self.context_digest is not None and not _valid_digest(self.context_digest):
            return _error(
                "HANDOFF_RECORD_INVALID",
                "context_digest must be a SHA-256 digest or null.",
            )
        if not isinstance(self.status, str) or self.status not in _STATUSES:
            return _error("HANDOFF_RECORD_INVALID", "status is not supported.")
        if self.target_goal_id is not None and not _valid_text(
            self.target_goal_id, max_length=_MAX_IDENTIFIER_LENGTH
        ):
            return _error(
                "HANDOFF_RECORD_INVALID", "target_goal_id must be bounded text."
            )
        if self.error_type is not None and not _valid_text(
            self.error_type, max_length=_MAX_ERROR_TYPE_LENGTH
        ):
            return _error("HANDOFF_RECORD_INVALID", "error_type must be bounded text.")
        try:
            _copy_result(self.result)
        except ValueError:
            return _error(
                "HANDOFF_RECORD_INVALID",
                "result must be a bounded JSON object or null.",
            )
        if not _finite_number(self.created_at) or not _finite_number(self.updated_at):
            return _error("HANDOFF_RECORD_INVALID", "timestamps must be finite.")
        if self.status == "pending":
            if self.owner_id != self.source_agent_id or self.target_goal_id is not None:
                return _error(
                    "HANDOFF_RECORD_INVALID",
                    "pending handoffs must be owned by the source without a goal.",
                )
            if self.error_type is not None:
                return _error(
                    "HANDOFF_RECORD_INVALID",
                    "pending handoffs cannot contain an error.",
                )
            if self.result is not None:
                return _error(
                    "HANDOFF_RECORD_INVALID",
                    "pending handoffs cannot contain a result.",
                )
        elif self.status == "accepted":
            if self.owner_id != self.target_agent_id or self.target_goal_id is not None:
                return _error(
                    "HANDOFF_RECORD_INVALID",
                    "accepted handoffs must be owned by the target.",
                )
            if self.error_type is not None:
                return _error(
                    "HANDOFF_RECORD_INVALID",
                    "accepted handoffs cannot contain an error.",
                )
            if self.result is not None:
                return _error(
                    "HANDOFF_RECORD_INVALID",
                    "accepted handoffs cannot contain a result.",
                )
        elif self.status == "completed":
            if self.owner_id != self.source_agent_id or self.target_goal_id is None:
                return _error(
                    "HANDOFF_RECORD_INVALID",
                    "completed handoffs must return ownership with a goal.",
                )
            if self.error_type is not None:
                return _error(
                    "HANDOFF_RECORD_INVALID",
                    "completed handoffs cannot contain an error.",
                )
        elif self.status == "failed":
            if (
                self.owner_id != self.source_agent_id
                or self.error_type is None
                or self.target_goal_id is not None
            ):
                return _error(
                    "HANDOFF_RECORD_INVALID",
                    "failed handoffs must return ownership with an error.",
                )
            if self.result is not None:
                return _error(
                    "HANDOFF_RECORD_INVALID",
                    "failed handoffs cannot contain a result.",
                )
        return None

    def to_dict(self, *, include_result: bool = True) -> Dict[str, Any]:
        """Return a JSON-compatible record without task or context contents."""
        payload: Dict[str, Any] = {
            "handoff_id": self.handoff_id,
            "source_agent_id": self.source_agent_id,
            "target_agent_id": self.target_agent_id,
            "task_digest": self.task_digest,
            "context_digest": self.context_digest,
            "status": self.status,
            "owner_id": self.owner_id,
            "target_goal_id": self.target_goal_id,
            "error_type": self.error_type,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }
        if include_result:
            payload["result"] = _copy_result(self.result)
        return payload

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "HandoffRecord":
        if not isinstance(data, Mapping):
            raise ValueError("handoff record must be an object")
        required = (
            "handoff_id",
            "source_agent_id",
            "target_agent_id",
            "task_digest",
            "context_digest",
            "status",
            "owner_id",
            "target_goal_id",
            "error_type",
            "created_at",
            "updated_at",
        )
        if any(name not in data for name in required):
            raise ValueError("handoff record is missing a required field")
        try:
            result = _copy_result(data.get("result"))
        except ValueError as exc:
            raise ValueError(str(exc)) from exc
        record = cls(
            handoff_id=data["handoff_id"],
            source_agent_id=data["source_agent_id"],
            target_agent_id=data["target_agent_id"],
            task_digest=data["task_digest"],
            context_digest=data["context_digest"],
            status=data["status"],
            owner_id=data["owner_id"],
            target_goal_id=data["target_goal_id"],
            error_type=data["error_type"],
            result=result,
            created_at=data["created_at"],
            updated_at=data["updated_at"],
        )
        validation = record.validate()
        if validation is not None:
            raise ValueError(validation["message"])
        return record


class HandoffStore(Protocol):
    """Persistence contract for local handoff identity and ownership."""

    def create(self, record: HandoffRecord) -> Result[HandoffRecord, Error]: ...

    def get(self, handoff_id: str) -> Result[Optional[HandoffRecord], Error]: ...

    def accept(
        self, handoff_id: str, target_agent_id: str
    ) -> Result[HandoffRecord, Error]: ...

    def complete(
        self,
        handoff_id: str,
        target_agent_id: str,
        target_goal_id: str,
        *,
        result: Optional[Mapping[str, Any]] = None,
    ) -> Result[HandoffRecord, Error]: ...

    def fail(
        self, handoff_id: str, target_agent_id: str, error_type: str
    ) -> Result[HandoffRecord, Error]: ...

    def list_open(
        self, limit: int = _MAX_LIST_LIMIT
    ) -> Result[List[HandoffRecord], Error]: ...


def _copy_record(record: HandoffRecord) -> HandoffRecord:
    return HandoffRecord.from_dict(record.to_dict())


def _validate_id(value: Any, name: str) -> Optional[Error]:
    if not _valid_text(value, max_length=_MAX_IDENTIFIER_LENGTH):
        return _error("HANDOFF_INPUT_INVALID", f"{name} must be bounded text.")
    return None


def _validate_error_type(value: Any) -> Optional[Error]:
    if not _valid_text(value, max_length=_MAX_ERROR_TYPE_LENGTH):
        return _error("HANDOFF_INPUT_INVALID", "error_type must be bounded text.")
    return None


def _validate_limit(limit: Any) -> Optional[Error]:
    if (
        not isinstance(limit, int)
        or isinstance(limit, bool)
        or not 0 < limit <= _MAX_LIST_LIMIT
    ):
        return _error("HANDOFF_LIMIT_INVALID", "list limit is out of bounds.")
    return None


def _state_error(message: str, record: HandoffRecord) -> Error:
    return _error(
        "HANDOFF_STATE_CONFLICT",
        message,
        status=record.status,
        owner_id=record.owner_id,
    )


class InMemoryHandoffStore:
    """Thread-safe bounded handoff store for local coordination."""

    def __init__(self) -> None:
        self._records: Dict[str, HandoffRecord] = {}
        self._lock = threading.RLock()

    def create(self, record: HandoffRecord) -> Result[HandoffRecord, Error]:
        validation = record.validate()
        if validation is not None:
            return Result.err(validation)
        candidate = _copy_record(record)
        with self._lock:
            existing = self._records.get(candidate.handoff_id)
            if existing is not None:
                same_identity = (
                    existing.source_agent_id == candidate.source_agent_id
                    and existing.target_agent_id == candidate.target_agent_id
                    and existing.task_digest == candidate.task_digest
                    and existing.context_digest == candidate.context_digest
                )
                if not same_identity:
                    return Result.err(
                        _error(
                            "HANDOFF_CONFLICT",
                            "handoff ID is already bound to another identity.",
                        )
                    )
                return Result.ok(_copy_record(existing))
            self._records[candidate.handoff_id] = candidate
            return Result.ok(_copy_record(candidate))

    def get(self, handoff_id: str) -> Result[Optional[HandoffRecord], Error]:
        identifier_error = _validate_id(handoff_id, "handoff_id")
        if identifier_error is not None:
            return Result.err(identifier_error)
        with self._lock:
            record = self._records.get(handoff_id)
            return Result.ok(None if record is None else _copy_record(record))

    def accept(
        self, handoff_id: str, target_agent_id: str
    ) -> Result[HandoffRecord, Error]:
        return self._transition(
            handoff_id,
            target_agent_id,
            lambda record: replace(
                record,
                status="accepted",
                owner_id=target_agent_id,
                updated_at=time.time(),
            ),
            expected_status="pending",
            expected_owner="source",
        )

    def complete(
        self,
        handoff_id: str,
        target_agent_id: str,
        target_goal_id: str,
        *,
        result: Optional[Mapping[str, Any]] = None,
    ) -> Result[HandoffRecord, Error]:
        goal_error = _validate_id(target_goal_id, "target_goal_id")
        if goal_error is not None:
            return Result.err(goal_error)
        try:
            copied_result = _copy_result(result)
        except ValueError as exc:
            return Result.err(
                _error(
                    "HANDOFF_RESULT_INVALID",
                    "handoff result is invalid.",
                    reason=str(exc),
                )
            )
        return self._transition(
            handoff_id,
            target_agent_id,
            lambda record: replace(
                record,
                status="completed",
                owner_id=record.source_agent_id,
                target_goal_id=target_goal_id,
                result=copied_result,
                updated_at=time.time(),
            ),
            expected_status="accepted",
            expected_owner="target",
        )

    def fail(
        self, handoff_id: str, target_agent_id: str, error_type: str
    ) -> Result[HandoffRecord, Error]:
        error_type_error = _validate_error_type(error_type)
        if error_type_error is not None:
            return Result.err(error_type_error)
        return self._transition(
            handoff_id,
            target_agent_id,
            lambda record: replace(
                record,
                status="failed",
                owner_id=record.source_agent_id,
                error_type=error_type,
                updated_at=time.time(),
            ),
            expected_status="accepted",
            expected_owner="target",
        )

    def list_open(
        self, limit: int = _MAX_LIST_LIMIT
    ) -> Result[List[HandoffRecord], Error]:
        limit_error = _validate_limit(limit)
        if limit_error is not None:
            return Result.err(limit_error)
        with self._lock:
            records = sorted(
                (
                    record
                    for record in self._records.values()
                    if record.status in {"pending", "accepted"}
                ),
                key=lambda record: (record.created_at, record.handoff_id),
            )
            return Result.ok([_copy_record(record) for record in records[:limit]])

    def _transition(
        self,
        handoff_id: str,
        target_agent_id: str,
        transition: Callable[[HandoffRecord], HandoffRecord],
        *,
        expected_status: str,
        expected_owner: str,
    ) -> Result[HandoffRecord, Error]:
        identifier_error = _validate_id(handoff_id, "handoff_id")
        if identifier_error is not None:
            return Result.err(identifier_error)
        target_error = _validate_id(target_agent_id, "target_agent_id")
        if target_error is not None:
            return Result.err(target_error)
        with self._lock:
            record = self._records.get(handoff_id)
            if record is None:
                return Result.err(_error("HANDOFF_NOT_FOUND", "handoff was not found."))
            if record.target_agent_id != target_agent_id:
                return Result.err(
                    _error(
                        "HANDOFF_OWNER_ERROR", "target agent does not own this handoff."
                    )
                )
            expected_owner_id = (
                record.source_agent_id
                if expected_owner == "source"
                else target_agent_id
            )
            if record.status != expected_status or record.owner_id != expected_owner_id:
                return Result.err(
                    _state_error("handoff is not in the expected state.", record)
                )
            updated = transition(record)
            validation = updated.validate()
            if validation is not None:
                return Result.err(validation)
            self._records[handoff_id] = updated
            return Result.ok(_copy_record(updated))


class FileHandoffStore:
    """Atomic JSON-file handoff store with per-record fencing leases."""

    def __init__(
        self,
        directory: Union[str, Path],
        max_record_bytes: int = _MAX_RECORD_BYTES,
        *,
        lease_manager: Optional[FileLeaseManager] = None,
        lease_ttl_seconds: float = _LEASE_TTL_SECONDS,
    ) -> None:
        if (
            not isinstance(max_record_bytes, int)
            or isinstance(max_record_bytes, bool)
            or max_record_bytes <= 0
        ):
            raise ValueError("max_record_bytes must be positive")
        self.directory = Path(directory).expanduser().resolve()
        self.directory.mkdir(parents=True, exist_ok=True)
        self.max_record_bytes = max_record_bytes
        self._lock = threading.RLock()
        self._record_leases = DurableRecordLease(
            self.directory,
            namespace="handoff",
            holder_label="handoff",
            lease_manager=lease_manager,
            lease_ttl_seconds=lease_ttl_seconds,
        )

    def _with_record_lease(
        self,
        handoff_id: str,
        operation: str,
        callback: Callable[[], Result[Any, Error]],
    ) -> Result[Any, Error]:
        return self._record_leases.run(
            handoff_id,
            operation,
            callback,
            acquire_error_type="HANDOFF_LEASE_ERROR",
            acquire_error_message="handoff record lease is unavailable.",
            release_error_type="HANDOFF_LEASE_RELEASE_ERROR",
            release_error_message="handoff record lease could not be released safely.",
        )

    def _path(self, handoff_id: str) -> Path:
        identifier_error = _validate_id(handoff_id, "handoff_id")
        if identifier_error is not None:
            raise ValueError(identifier_error["message"])
        path = (self.directory / f"{handoff_id}.json").resolve()
        if self.directory not in path.parents:
            raise ValueError("handoff path escapes the configured directory")
        return path

    def _read_unlocked(self, handoff_id: str) -> Optional[HandoffRecord]:
        path = self._path(handoff_id)
        if not path.exists():
            return None
        if path.stat().st_size > self.max_record_bytes:
            raise ValueError("handoff record exceeds configured size limit")
        with path.open("r", encoding="utf-8") as handle:
            return HandoffRecord.from_dict(json.load(handle))

    def _write_unlocked(self, record: HandoffRecord) -> HandoffRecord:
        payload = json.dumps(
            record.to_dict(), ensure_ascii=False, allow_nan=False, indent=2
        )
        if len(payload.encode("utf-8")) > self.max_record_bytes:
            raise ValueError("handoff record exceeds configured size limit")
        temporary_path: Optional[Path] = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                dir=str(self.directory),
                prefix=f".{record.handoff_id}.",
                suffix=".tmp",
                delete=False,
            ) as handle:
                temporary_path = Path(handle.name)
                handle.write(payload)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(str(temporary_path), str(self._path(record.handoff_id)))
            temporary_path = None
        finally:
            if temporary_path is not None:
                try:
                    temporary_path.unlink()
                except OSError:
                    pass
        return _copy_record(record)

    def get(self, handoff_id: str) -> Result[Optional[HandoffRecord], Error]:
        return self._with_record_lease(
            handoff_id, "get", lambda: self._get_without_lease(handoff_id)
        )

    def _get_without_lease(
        self, handoff_id: str
    ) -> Result[Optional[HandoffRecord], Error]:
        try:
            with self._lock:
                record = self._read_unlocked(handoff_id)
                return Result.ok(None if record is None else _copy_record(record))
        except (OSError, TypeError, ValueError, json.JSONDecodeError) as exc:
            return Result.err(
                _error(
                    "HANDOFF_LOAD_ERROR",
                    "failed to load handoff record.",
                    reason=str(exc)[:256],
                )
            )

    def create(self, record: HandoffRecord) -> Result[HandoffRecord, Error]:
        validation = record.validate()
        if validation is not None:
            return Result.err(validation)
        return self._with_record_lease(
            record.handoff_id,
            "create",
            lambda: self._create_without_lease(record),
        )

    def _create_without_lease(
        self, record: HandoffRecord
    ) -> Result[HandoffRecord, Error]:
        try:
            with self._lock:
                existing = self._read_unlocked(record.handoff_id)
                if existing is not None:
                    same_identity = (
                        existing.source_agent_id == record.source_agent_id
                        and existing.target_agent_id == record.target_agent_id
                        and existing.task_digest == record.task_digest
                        and existing.context_digest == record.context_digest
                    )
                    if not same_identity:
                        return Result.err(
                            _error(
                                "HANDOFF_CONFLICT",
                                "handoff ID is already bound to another identity.",
                            )
                        )
                    return Result.ok(_copy_record(existing))
                return Result.ok(self._write_unlocked(record))
        except (OSError, TypeError, ValueError, json.JSONDecodeError) as exc:
            return Result.err(
                _error(
                    "HANDOFF_SAVE_ERROR",
                    "failed to save handoff record.",
                    reason=str(exc)[:256],
                )
            )

    def accept(
        self, handoff_id: str, target_agent_id: str
    ) -> Result[HandoffRecord, Error]:
        return self._transition(handoff_id, target_agent_id, "accept")

    def complete(
        self,
        handoff_id: str,
        target_agent_id: str,
        target_goal_id: str,
        *,
        result: Optional[Mapping[str, Any]] = None,
    ) -> Result[HandoffRecord, Error]:
        goal_error = _validate_id(target_goal_id, "target_goal_id")
        if goal_error is not None:
            return Result.err(goal_error)
        try:
            copied_result = _copy_result(result)
        except ValueError as exc:
            return Result.err(
                _error(
                    "HANDOFF_RESULT_INVALID",
                    "handoff result is invalid.",
                    reason=str(exc),
                )
            )
        return self._transition(
            handoff_id,
            target_agent_id,
            "complete",
            target_goal_id=target_goal_id,
            result=copied_result,
        )

    def fail(
        self, handoff_id: str, target_agent_id: str, error_type: str
    ) -> Result[HandoffRecord, Error]:
        error_type_error = _validate_error_type(error_type)
        if error_type_error is not None:
            return Result.err(error_type_error)
        return self._transition(
            handoff_id,
            target_agent_id,
            "fail",
            error_type=error_type,
        )

    def _transition(
        self,
        handoff_id: str,
        target_agent_id: str,
        operation: str,
        *,
        target_goal_id: Optional[str] = None,
        error_type: Optional[str] = None,
        result: Optional[Mapping[str, Any]] = None,
    ) -> Result[HandoffRecord, Error]:
        identifier_error = _validate_id(handoff_id, "handoff_id")
        if identifier_error is not None:
            return Result.err(identifier_error)
        target_error = _validate_id(target_agent_id, "target_agent_id")
        if target_error is not None:
            return Result.err(target_error)
        return self._with_record_lease(
            handoff_id,
            operation,
            lambda: self._transition_without_lease(
                handoff_id,
                target_agent_id,
                operation,
                target_goal_id=target_goal_id,
                error_type=error_type,
                result=result,
            ),
        )

    def _transition_without_lease(
        self,
        handoff_id: str,
        target_agent_id: str,
        operation: str,
        *,
        target_goal_id: Optional[str],
        error_type: Optional[str],
        result: Optional[Mapping[str, Any]],
    ) -> Result[HandoffRecord, Error]:
        try:
            with self._lock:
                record = self._read_unlocked(handoff_id)
                if record is None:
                    return Result.err(
                        _error("HANDOFF_NOT_FOUND", "handoff was not found.")
                    )
                if record.target_agent_id != target_agent_id:
                    return Result.err(
                        _error(
                            "HANDOFF_OWNER_ERROR",
                            "target agent does not own this handoff.",
                        )
                    )
                if operation == "accept":
                    if (
                        record.status != "pending"
                        or record.owner_id != record.source_agent_id
                    ):
                        return Result.err(
                            _state_error(
                                "handoff is not in the expected state.", record
                            )
                        )
                    updated = replace(
                        record,
                        status="accepted",
                        owner_id=target_agent_id,
                        updated_at=time.time(),
                    )
                elif operation == "complete":
                    if (
                        record.status != "accepted"
                        or record.owner_id != target_agent_id
                    ):
                        return Result.err(
                            _state_error(
                                "handoff is not in the expected state.", record
                            )
                        )
                    updated = replace(
                        record,
                        status="completed",
                        owner_id=record.source_agent_id,
                        target_goal_id=target_goal_id,
                        result=dict(result) if result is not None else None,
                        updated_at=time.time(),
                    )
                else:
                    if (
                        record.status != "accepted"
                        or record.owner_id != target_agent_id
                    ):
                        return Result.err(
                            _state_error(
                                "handoff is not in the expected state.", record
                            )
                        )
                    updated = replace(
                        record,
                        status="failed",
                        owner_id=record.source_agent_id,
                        error_type=error_type,
                        updated_at=time.time(),
                    )
                validation = updated.validate()
                if validation is not None:
                    return Result.err(validation)
                return Result.ok(self._write_unlocked(updated))
        except (OSError, TypeError, ValueError, json.JSONDecodeError) as exc:
            return Result.err(
                _error(
                    "HANDOFF_SAVE_ERROR",
                    "failed to update handoff record.",
                    reason=str(exc)[:256],
                )
            )

    def list_open(
        self, limit: int = _MAX_LIST_LIMIT
    ) -> Result[List[HandoffRecord], Error]:
        limit_error = _validate_limit(limit)
        if limit_error is not None:
            return Result.err(limit_error)
        try:
            paths = sorted(self.directory.glob("*.json"), key=lambda path: path.name)
            records: List[HandoffRecord] = []
            for path in paths:
                if len(records) >= limit:
                    break
                handoff_id = path.stem
                loaded = self.get(handoff_id)
                if loaded.is_err():
                    return Result.err(loaded.unwrap_err())
                record = loaded.unwrap()
                if record is not None and record.status in {"pending", "accepted"}:
                    records.append(record)
            records.sort(key=lambda record: (record.created_at, record.handoff_id))
            return Result.ok(records[:limit])
        except (OSError, TypeError, ValueError) as exc:
            return Result.err(
                _error(
                    "HANDOFF_LOAD_ERROR",
                    "failed to list handoff records.",
                    reason=str(exc)[:256],
                )
            )
