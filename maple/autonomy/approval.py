"""Durable, fail-closed approval records for autonomous tool actions."""

from __future__ import annotations

import json
import math
import os
import re
import tempfile
import threading
import time
import uuid
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Protocol, Union

from ..core.result import Result
from ..resources.lease import FileLeaseManager

_IDENTIFIER = re.compile(r"^[A-Za-z0-9_.:-]{1,128}$")
_STATUSES = {"pending", "approved", "denied", "consumed"}
_MAX_ARGUMENT_BYTES = 65_536
_MAX_ARGUMENT_DEPTH = 16
_MAX_ARGUMENT_ITEMS = 1_000
_MAX_LIST_LIMIT = 1_000
_MAX_LIST_SCAN = 10_000
_APPROVAL_LEASE_TTL_SECONDS = 30.0

Error = Dict[str, Any]


def _error(error_type: str, message: str, **details: Any) -> Error:
    result: Error = {"errorType": error_type, "message": message}
    if details:
        result["details"] = details
    return result


def _validate_json_value(
    value: Any,
    *,
    path: str = "$",
    depth: int = 0,
) -> Optional[Error]:
    if depth > _MAX_ARGUMENT_DEPTH:
        return _error(
            "APPROVAL_ARGUMENT_DEPTH", "Approval arguments are too deep.", path=path
        )
    if value is None or isinstance(value, (bool, int, str)):
        return None
    if isinstance(value, float):
        if not math.isfinite(value):
            return _error(
                "APPROVAL_ARGUMENT_VALUE",
                "Approval arguments contain a non-finite number.",
                path=path,
            )
        return None
    if isinstance(value, list):
        if len(value) > _MAX_ARGUMENT_ITEMS:
            return _error(
                "APPROVAL_ARGUMENT_SIZE",
                "Approval arguments contain too many list items.",
                path=path,
            )
        for index, item in enumerate(value):
            error = _validate_json_value(item, path=f"{path}[{index}]", depth=depth + 1)
            if error:
                return error
        return None
    if isinstance(value, dict):
        if len(value) > _MAX_ARGUMENT_ITEMS:
            return _error(
                "APPROVAL_ARGUMENT_SIZE",
                "Approval arguments contain too many object keys.",
                path=path,
            )
        for key, item in value.items():
            if not isinstance(key, str):
                return _error(
                    "APPROVAL_ARGUMENT_KEY",
                    "Approval argument keys must be strings.",
                    path=path,
                )
            error = _validate_json_value(item, path=f"{path}.{key}", depth=depth + 1)
            if error:
                return error
        return None
    return _error(
        "APPROVAL_ARGUMENT_VALUE",
        "Approval arguments must be JSON-compatible.",
        path=path,
    )


def _copy_arguments(arguments: Any) -> Result[Dict[str, Any], Error]:
    if not isinstance(arguments, dict):
        return Result.err(
            _error("APPROVAL_ARGUMENT_VALUE", "Approval arguments must be an object.")
        )
    error = _validate_json_value(arguments)
    if error:
        return Result.err(error)
    try:
        encoded = json.dumps(
            arguments, ensure_ascii=False, allow_nan=False, separators=(",", ":")
        )
        if len(encoded.encode("utf-8")) > _MAX_ARGUMENT_BYTES:
            return Result.err(
                _error(
                    "APPROVAL_ARGUMENT_SIZE",
                    "Approval arguments exceed the configured byte limit.",
                    max_bytes=_MAX_ARGUMENT_BYTES,
                )
            )
        return Result.ok(json.loads(encoded))
    except (TypeError, ValueError, json.JSONDecodeError) as exc:
        return Result.err(
            _error(
                "APPROVAL_ARGUMENT_VALUE",
                "Approval arguments are not JSON serializable.",
                reason=str(exc)[:256],
            )
        )


def _validate_edited_arguments(
    approved: bool, edited_arguments: Optional[Dict[str, Any]]
) -> Result[Optional[Dict[str, Any]], Error]:
    """Validate an optional operator replacement before a decision commits."""
    if edited_arguments is None:
        return Result.ok(None)
    if not approved:
        return Result.err(
            _error(
                "APPROVAL_DECISION_INVALID",
                "Edited arguments can only accompany an approval decision.",
            )
        )
    copied = _copy_arguments(edited_arguments)
    if copied.is_err():
        return Result.err(
            _error(
                "APPROVAL_DECISION_INVALID",
                "Edited arguments are invalid.",
                reason=copied.unwrap_err()["message"],
            )
        )
    return Result.ok(copied.unwrap())


def _valid_identifier(value: Any, field_name: str) -> Optional[Error]:
    if not isinstance(value, str) or not _IDENTIFIER.fullmatch(value):
        return _error(
            "INVALID_IDENTIFIER",
            f"{field_name} must contain 1-128 letters, numbers, '_', '.', ':', or '-'.",
            field=field_name,
        )
    return None


def _valid_text(value: Any, field_name: str) -> Optional[Error]:
    if not isinstance(value, str) or not value or len(value) > 256:
        return _error(
            "INVALID_APPROVAL_TEXT",
            f"{field_name} must be a non-empty string of at most 256 characters.",
            field=field_name,
        )
    return None


@dataclass(frozen=True)
class ApprovalDecision:
    """Immutable operator decision recorded against an approval request."""

    approval_id: str
    approved: bool
    decided_at: float
    edited_arguments: Optional[Dict[str, Any]] = None

    def __post_init__(self) -> None:
        if _valid_identifier(self.approval_id, "approval_id"):
            raise ValueError("invalid approval_id")
        if type(self.approved) is not bool:
            raise ValueError("approval decision must contain a boolean")
        if not math.isfinite(self.decided_at):
            raise ValueError("approval decision timestamp must be finite")
        if self.edited_arguments is not None:
            if not self.approved:
                raise ValueError("denying approval cannot contain edited arguments")
            arguments = _copy_arguments(self.edited_arguments)
            if arguments.is_err():
                raise ValueError(arguments.unwrap_err()["message"])
            object.__setattr__(self, "edited_arguments", arguments.unwrap())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "approval_id": self.approval_id,
            "approved": self.approved,
            "decided_at": self.decided_at,
            "edited_arguments": self.edited_arguments,
        }


@dataclass(frozen=True)
class ApprovalRequest:
    """JSON-safe durable record for one approval-gated tool call."""

    approval_id: str
    tool_call_id: str
    tool_name: str
    arguments: Dict[str, Any]
    status: str = "pending"
    created_at: float = 0.0
    updated_at: float = 0.0
    decision: Optional[ApprovalDecision] = None

    def __post_init__(self) -> None:
        now = time.time()
        if self.created_at == 0.0:
            object.__setattr__(self, "created_at", now)
        if self.updated_at == 0.0:
            object.__setattr__(self, "updated_at", now)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "approval_id": self.approval_id,
            "tool_call_id": self.tool_call_id,
            "tool_name": self.tool_name,
            "arguments": self.arguments,
            "status": self.status,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "decision": self.decision.to_dict() if self.decision else None,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ApprovalRequest":
        if not isinstance(data, dict):
            raise ValueError("approval request must be an object")
        for field_name in ("approval_id", "tool_call_id", "tool_name", "arguments"):
            if field_name not in data:
                raise ValueError("approval request is missing a required field")
        if _valid_identifier(data["approval_id"], "approval_id"):
            raise ValueError("invalid approval_id")
        if _valid_text(data["tool_call_id"], "tool_call_id"):
            raise ValueError("invalid tool_call_id")
        if _valid_text(data["tool_name"], "tool_name"):
            raise ValueError("invalid tool_name")
        arguments = _copy_arguments(data["arguments"])
        if arguments.is_err():
            raise ValueError(arguments.unwrap_err()["message"])
        status = data.get("status", "pending")
        if status not in _STATUSES:
            raise ValueError("invalid approval status")
        decision_data = data.get("decision")
        decision: Optional[ApprovalDecision] = None
        if decision_data is not None:
            if not isinstance(decision_data, dict):
                raise ValueError("approval decision must be an object or null")
            if decision_data.get("approval_id") != data["approval_id"]:
                raise ValueError("approval decision ID does not match request")
            if type(decision_data.get("approved")) is not bool:
                raise ValueError("approval decision must contain a boolean")
            decided_at = float(decision_data.get("decided_at", time.time()))
            if not math.isfinite(decided_at):
                raise ValueError("approval decision timestamp must be finite")
            edited_arguments_data = decision_data.get("edited_arguments")
            edited_arguments: Optional[Dict[str, Any]] = None
            if edited_arguments_data is not None:
                edited_arguments_result = _copy_arguments(edited_arguments_data)
                if edited_arguments_result.is_err():
                    raise ValueError(edited_arguments_result.unwrap_err()["message"])
                edited_arguments = edited_arguments_result.unwrap()
            decision = ApprovalDecision(
                approval_id=data["approval_id"],
                approved=decision_data["approved"],
                decided_at=decided_at,
                edited_arguments=edited_arguments,
            )
        if status == "pending" and decision is not None:
            raise ValueError("pending approval cannot contain a decision")
        if status in {"approved", "consumed"} and (
            decision is None or not decision.approved
        ):
            raise ValueError("approved approval must contain an approving decision")
        if status == "denied" and (decision is None or decision.approved):
            raise ValueError("denied approval must contain a denying decision")
        created_at = float(data.get("created_at", time.time()))
        updated_at = float(data.get("updated_at", time.time()))
        if not math.isfinite(created_at) or not math.isfinite(updated_at):
            raise ValueError("approval timestamps must be finite")
        return cls(
            approval_id=data["approval_id"],
            tool_call_id=data["tool_call_id"],
            tool_name=data["tool_name"],
            arguments=arguments.unwrap(),
            status=status,
            created_at=created_at,
            updated_at=updated_at,
            decision=decision,
        )


class ApprovalStore(Protocol):
    """Persistence contract for human approval requests."""

    def get(self, approval_id: str) -> Result[Optional[ApprovalRequest], Error]: ...

    def create(self, request: ApprovalRequest) -> Result[ApprovalRequest, Error]: ...

    def decide(
        self,
        approval_id: str,
        approved: bool,
        *,
        edited_arguments: Optional[Dict[str, Any]] = None,
    ) -> Result[ApprovalRequest, Error]: ...

    def consume(self, approval_id: str) -> Result[ApprovalRequest, Error]: ...

    def list_pending(
        self, limit: int = 100
    ) -> Result[List[ApprovalRequest], Error]: ...


def _copy_request(request: ApprovalRequest) -> ApprovalRequest:
    return ApprovalRequest.from_dict(request.to_dict())


class InMemoryApprovalStore:
    """Thread-safe approval store for local runs and contract tests."""

    def __init__(self) -> None:
        self._requests: Dict[str, ApprovalRequest] = {}
        self._lock = threading.RLock()

    def get(self, approval_id: str) -> Result[Optional[ApprovalRequest], Error]:
        identifier_error = _valid_identifier(approval_id, "approval_id")
        if identifier_error:
            return Result.err(identifier_error)
        with self._lock:
            request = self._requests.get(approval_id)
            return Result.ok(None if request is None else _copy_request(request))

    def create(self, request: ApprovalRequest) -> Result[ApprovalRequest, Error]:
        try:
            candidate = _copy_request(request)
        except (TypeError, ValueError) as exc:
            return Result.err(
                _error(
                    "APPROVAL_INVALID",
                    "Invalid approval request.",
                    reason=str(exc)[:256],
                )
            )
        if candidate.status != "pending":
            return Result.err(
                _error("APPROVAL_INVALID", "New approval requests must be pending.")
            )
        with self._lock:
            existing = self._requests.get(candidate.approval_id)
            if existing is not None:
                same_request = (
                    existing.tool_call_id == candidate.tool_call_id
                    and existing.tool_name == candidate.tool_name
                    and existing.arguments == candidate.arguments
                )
                if not same_request:
                    return Result.err(
                        _error(
                            "APPROVAL_CONFLICT",
                            "Approval ID is already bound to another tool call.",
                            approval_id=candidate.approval_id,
                        )
                    )
                return Result.ok(_copy_request(existing))
            self._requests[candidate.approval_id] = candidate
            return Result.ok(_copy_request(candidate))

    def decide(
        self,
        approval_id: str,
        approved: bool,
        *,
        edited_arguments: Optional[Dict[str, Any]] = None,
    ) -> Result[ApprovalRequest, Error]:
        return self._transition(
            approval_id, approved=approved, edited_arguments=edited_arguments
        )

    def consume(self, approval_id: str) -> Result[ApprovalRequest, Error]:
        identifier_error = _valid_identifier(approval_id, "approval_id")
        if identifier_error:
            return Result.err(identifier_error)
        with self._lock:
            request = self._requests.get(approval_id)
            if request is None:
                return Result.err(
                    _error("APPROVAL_NOT_FOUND", "Approval request was not found.")
                )
            if request.status != "approved":
                return Result.err(
                    _error(
                        "APPROVAL_NOT_APPROVED",
                        "Only an approved request can be consumed.",
                        status=request.status,
                    )
                )
            consumed = replace(request, status="consumed", updated_at=time.time())
            self._requests[approval_id] = consumed
            return Result.ok(_copy_request(consumed))

    def list_pending(self, limit: int = 100) -> Result[List[ApprovalRequest], Error]:
        if (
            not isinstance(limit, int)
            or isinstance(limit, bool)
            or not 0 < limit <= _MAX_LIST_LIMIT
        ):
            return Result.err(
                _error(
                    "APPROVAL_LIMIT_INVALID", "Approval list limit is out of bounds."
                )
            )
        with self._lock:
            pending = sorted(
                (
                    request
                    for request in self._requests.values()
                    if request.status == "pending"
                ),
                key=lambda request: (request.created_at, request.approval_id),
            )
            return Result.ok([_copy_request(request) for request in pending[:limit]])

    def _transition(
        self,
        approval_id: str,
        *,
        approved: bool,
        edited_arguments: Optional[Dict[str, Any]] = None,
    ) -> Result[ApprovalRequest, Error]:
        identifier_error = _valid_identifier(approval_id, "approval_id")
        if identifier_error:
            return Result.err(identifier_error)
        if type(approved) is not bool:
            return Result.err(
                _error("APPROVAL_DECISION_INVALID", "Decision must be boolean.")
            )
        edited_arguments_result = _validate_edited_arguments(approved, edited_arguments)
        if edited_arguments_result.is_err():
            return Result.err(edited_arguments_result.unwrap_err())
        with self._lock:
            request = self._requests.get(approval_id)
            if request is None:
                return Result.err(
                    _error("APPROVAL_NOT_FOUND", "Approval request was not found.")
                )
            if request.status != "pending":
                return Result.err(
                    _error(
                        "APPROVAL_CONFLICT",
                        "Approval request already has a terminal state.",
                        status=request.status,
                    )
                )
            decision = ApprovalDecision(
                approval_id,
                approved,
                time.time(),
                edited_arguments_result.unwrap(),
            )
            decided = replace(
                request,
                status="approved" if approved else "denied",
                updated_at=decision.decided_at,
                decision=decision,
            )
            self._requests[approval_id] = decided
            return Result.ok(_copy_request(decided))


class FileApprovalStore:
    """Atomic JSON-file approval store for process-restart human handoff.

    The store is thread-safe within one process and acquires a short-lived
    per-record fencing lease from a caller-owned file lease directory before
    each read/modify/write operation. Notifications remain a host
    responsibility.
    """

    def __init__(
        self,
        directory: Union[str, Path],
        max_record_bytes: int = 262_144,
        *,
        lease_manager: Optional[FileLeaseManager] = None,
        lease_ttl_seconds: float = _APPROVAL_LEASE_TTL_SECONDS,
    ) -> None:
        if max_record_bytes <= 0:
            raise ValueError("max_record_bytes must be positive")
        if (
            not isinstance(lease_ttl_seconds, (int, float))
            or isinstance(lease_ttl_seconds, bool)
            or lease_ttl_seconds <= 0
        ):
            raise ValueError("lease_ttl_seconds must be positive")
        self.directory = Path(directory).expanduser().resolve()
        self.directory.mkdir(parents=True, exist_ok=True)
        self.max_record_bytes = max_record_bytes
        self._lock = threading.RLock()
        self._lease_manager = lease_manager or FileLeaseManager(
            self.directory / ".maple-leases"
        )
        self._lease_holder = f"approval-store-{os.getpid()}-{uuid.uuid4().hex}"
        self._lease_ttl_seconds = float(lease_ttl_seconds)

    def _lease_resource(self, approval_id: str) -> str:
        return f"approval:{approval_id}"

    def _lease_failure(self, operation: str, error: Any) -> Error:
        reason = "unknown"
        if isinstance(error, dict):
            reason = str(error.get("errorType", "unknown"))[:64]
        return _error(
            "APPROVAL_LEASE_ERROR",
            "Approval record lease is unavailable.",
            operation=operation,
            reason=reason,
        )

    def _lease_release_failure(self, operation: str, error: Any) -> Error:
        reason = "unknown"
        if isinstance(error, dict):
            reason = str(error.get("errorType", "unknown"))[:64]
        return _error(
            "APPROVAL_LEASE_RELEASE_ERROR",
            "Approval record lease could not be released safely.",
            operation=operation,
            reason=reason,
        )

    def _with_record_lease(
        self,
        approval_id: str,
        operation: str,
        callback: Callable[[], Result[Any, Error]],
    ) -> Result[Any, Error]:
        try:
            acquired = self._lease_manager.acquire(
                self._lease_resource(approval_id),
                self._lease_holder,
                self._lease_ttl_seconds,
            )
        except (OSError, TypeError, ValueError) as exc:
            return Result.err(self._lease_failure(operation, type(exc).__name__))
        if acquired.is_err():
            return Result.err(self._lease_failure(operation, acquired.unwrap_err()))
        lease = acquired.unwrap()
        result: Optional[Result[Any, Error]] = None
        operation_exception: Optional[Exception] = None
        release_result: Optional[Result[Any, Any]] = None
        release_exception: Optional[Exception] = None
        try:
            try:
                result = callback()
            except Exception as exc:
                operation_exception = exc
        finally:
            try:
                release_result = self._lease_manager.release(lease)
            except Exception as exc:
                release_exception = exc
        if operation_exception is not None:
            if release_exception is not None:
                raise release_exception from operation_exception
            if release_result is not None and (
                release_result.is_err() or release_result.unwrap() is not True
            ):
                raise RuntimeError(
                    "approval record lease release failed"
                ) from operation_exception
            raise operation_exception
        if release_exception is not None:
            raise release_exception
        if result is None:
            raise RuntimeError("approval lease callback returned no result")
        if release_result is not None and (
            release_result.is_err() or release_result.unwrap() is not True
        ):
            release_error = self._lease_release_failure(
                operation,
                (
                    release_result.unwrap_err()
                    if release_result.is_err()
                    else {"errorType": "LEASE_NOT_HELD"}
                ),
            )
            if result.is_err():
                existing = dict(result.unwrap_err())
                details = existing.get("details")
                merged_details = dict(details) if isinstance(details, dict) else {}
                merged_details["lease_release_error"] = release_error["errorType"]
                existing["details"] = merged_details
                return Result.err(existing)
            return Result.err(release_error)
        return result

    def _path(self, approval_id: str) -> Path:
        identifier_error = _valid_identifier(approval_id, "approval_id")
        if identifier_error:
            raise ValueError(identifier_error["message"])
        path = (self.directory / f"{approval_id}.json").resolve()
        if self.directory not in path.parents:
            raise ValueError("approval path escapes the configured directory")
        return path

    def _read_unlocked(self, approval_id: str) -> Optional[ApprovalRequest]:
        path = self._path(approval_id)
        if not path.exists():
            return None
        if path.stat().st_size > self.max_record_bytes:
            raise ValueError("approval record exceeds configured size limit")
        with path.open("r", encoding="utf-8") as handle:
            return ApprovalRequest.from_dict(json.load(handle))

    def _write_unlocked(self, request: ApprovalRequest) -> ApprovalRequest:
        payload = json.dumps(
            request.to_dict(), ensure_ascii=False, allow_nan=False, indent=2
        )
        if len(payload.encode("utf-8")) > self.max_record_bytes:
            raise ValueError("approval record exceeds configured size limit")
        temporary_path: Optional[Path] = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                dir=str(self.directory),
                prefix=f".{request.approval_id}.",
                suffix=".tmp",
                delete=False,
            ) as handle:
                temporary_path = Path(handle.name)
                handle.write(payload)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(str(temporary_path), str(self._path(request.approval_id)))
            temporary_path = None
        finally:
            if temporary_path is not None:
                try:
                    temporary_path.unlink()
                except OSError:
                    pass
        return _copy_request(request)

    def get(self, approval_id: str) -> Result[Optional[ApprovalRequest], Error]:
        return self._with_record_lease(
            approval_id,
            "get",
            lambda: self._get_without_lease(approval_id),
        )

    def _get_without_lease(
        self, approval_id: str
    ) -> Result[Optional[ApprovalRequest], Error]:
        try:
            with self._lock:
                request = self._read_unlocked(approval_id)
                return Result.ok(None if request is None else _copy_request(request))
        except (OSError, TypeError, ValueError, json.JSONDecodeError) as exc:
            return Result.err(
                _error(
                    "APPROVAL_LOAD_ERROR",
                    "Failed to load approval request.",
                    reason=str(exc)[:256],
                )
            )

    def create(self, request: ApprovalRequest) -> Result[ApprovalRequest, Error]:
        return self._with_record_lease(
            request.approval_id,
            "create",
            lambda: self._create_without_lease(request),
        )

    def _create_without_lease(
        self, request: ApprovalRequest
    ) -> Result[ApprovalRequest, Error]:
        try:
            candidate = _copy_request(request)
            if candidate.status != "pending":
                return Result.err(
                    _error("APPROVAL_INVALID", "New approval requests must be pending.")
                )
            with self._lock:
                existing = self._read_unlocked(candidate.approval_id)
                if existing is not None:
                    same_request = (
                        existing.tool_call_id == candidate.tool_call_id
                        and existing.tool_name == candidate.tool_name
                        and existing.arguments == candidate.arguments
                    )
                    if not same_request:
                        return Result.err(
                            _error(
                                "APPROVAL_CONFLICT",
                                "Approval ID is already bound to another tool call.",
                            )
                        )
                    return Result.ok(_copy_request(existing))
                return Result.ok(self._write_unlocked(candidate))
        except (OSError, TypeError, ValueError, json.JSONDecodeError) as exc:
            return Result.err(
                _error(
                    "APPROVAL_SAVE_ERROR",
                    "Failed to save approval request.",
                    reason=str(exc)[:256],
                )
            )

    def decide(
        self,
        approval_id: str,
        approved: bool,
        *,
        edited_arguments: Optional[Dict[str, Any]] = None,
    ) -> Result[ApprovalRequest, Error]:
        return self._with_record_lease(
            approval_id,
            "decide",
            lambda: self._decide_without_lease(
                approval_id, approved, edited_arguments=edited_arguments
            ),
        )

    def _decide_without_lease(
        self,
        approval_id: str,
        approved: bool,
        *,
        edited_arguments: Optional[Dict[str, Any]] = None,
    ) -> Result[ApprovalRequest, Error]:
        if type(approved) is not bool:
            return Result.err(
                _error("APPROVAL_DECISION_INVALID", "Decision must be boolean.")
            )
        edited_arguments_result = _validate_edited_arguments(approved, edited_arguments)
        if edited_arguments_result.is_err():
            return Result.err(edited_arguments_result.unwrap_err())
        try:
            with self._lock:
                request = self._read_unlocked(approval_id)
                if request is None:
                    return Result.err(
                        _error("APPROVAL_NOT_FOUND", "Approval request was not found.")
                    )
                if request.status != "pending":
                    return Result.err(
                        _error(
                            "APPROVAL_CONFLICT",
                            "Approval request already has a terminal state.",
                            status=request.status,
                        )
                    )
                decision = ApprovalDecision(
                    approval_id,
                    approved,
                    time.time(),
                    edited_arguments_result.unwrap(),
                )
                decided = replace(
                    request,
                    status="approved" if approved else "denied",
                    updated_at=decision.decided_at,
                    decision=decision,
                )
                return Result.ok(self._write_unlocked(decided))
        except (OSError, TypeError, ValueError, json.JSONDecodeError) as exc:
            return Result.err(
                _error(
                    "APPROVAL_SAVE_ERROR",
                    "Failed to save approval decision.",
                    reason=str(exc)[:256],
                )
            )

    def consume(self, approval_id: str) -> Result[ApprovalRequest, Error]:
        return self._with_record_lease(
            approval_id,
            "consume",
            lambda: self._consume_without_lease(approval_id),
        )

    def _consume_without_lease(
        self, approval_id: str
    ) -> Result[ApprovalRequest, Error]:
        try:
            with self._lock:
                request = self._read_unlocked(approval_id)
                if request is None:
                    return Result.err(
                        _error("APPROVAL_NOT_FOUND", "Approval request was not found.")
                    )
                if request.status != "approved":
                    return Result.err(
                        _error(
                            "APPROVAL_NOT_APPROVED",
                            "Only an approved request can be consumed.",
                            status=request.status,
                        )
                    )
                consumed = replace(request, status="consumed", updated_at=time.time())
                return Result.ok(self._write_unlocked(consumed))
        except (OSError, TypeError, ValueError, json.JSONDecodeError) as exc:
            return Result.err(
                _error(
                    "APPROVAL_SAVE_ERROR",
                    "Failed to consume approval request.",
                    reason=str(exc)[:256],
                )
            )

    def list_pending(self, limit: int = 100) -> Result[List[ApprovalRequest], Error]:
        return self._with_record_lease(
            "__list__",
            "list_pending",
            lambda: self._list_pending_without_lease(limit),
        )

    def _list_pending_without_lease(
        self, limit: int = 100
    ) -> Result[List[ApprovalRequest], Error]:
        if (
            not isinstance(limit, int)
            or isinstance(limit, bool)
            or not 0 < limit <= _MAX_LIST_LIMIT
        ):
            return Result.err(
                _error(
                    "APPROVAL_LIMIT_INVALID", "Approval list limit is out of bounds."
                )
            )
        try:
            with self._lock:
                paths = []
                for path in self.directory.iterdir():
                    if path.suffix == ".json":
                        paths.append(path)
                        if len(paths) >= _MAX_LIST_SCAN:
                            break
                pending = []
                for path in paths:
                    request = self._read_unlocked(path.stem)
                    if request is not None and request.status == "pending":
                        pending.append(request)
                pending.sort(
                    key=lambda request: (request.created_at, request.approval_id)
                )
                return Result.ok(
                    [_copy_request(request) for request in pending[:limit]]
                )
        except (OSError, TypeError, ValueError, json.JSONDecodeError) as exc:
            return Result.err(
                _error(
                    "APPROVAL_LOAD_ERROR",
                    "Failed to list approval requests.",
                    reason=str(exc)[:256],
                )
            )
