"""Bounded durable request/response records for human-in-the-loop runs."""

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
from typing import Any, Dict, List, Mapping, Optional, Protocol, Union

from ..core.result import Result
from .contracts import validate_json_schema

Error = Dict[str, Any]

_IDENTIFIER = re.compile(r"^[A-Za-z0-9_.:-]{1,128}$")
_STATUSES = {"pending", "responded", "rejected", "consumed"}
_MAX_PROMPT_LENGTH = 4_096
_MAX_REASON_LENGTH = 256
_MAX_RECORD_BYTES = 262_144
_MAX_JSON_DEPTH = 16
_MAX_JSON_ITEMS = 10_000
_MAX_LIST_LIMIT = 1_000
_MAX_LIST_SCAN = 10_000


def _error(error_type: str, message: str, **details: Any) -> Error:
    result: Error = {"errorType": error_type, "message": message}
    if details:
        result["details"] = details
    return result


def _copy_json(
    value: Any,
    *,
    path: str = "$",
    depth: int = 0,
) -> Result[Any, Error]:
    if depth > _MAX_JSON_DEPTH:
        return Result.err(
            _error(
                "HUMAN_INPUT_VALUE_TOO_DEEP",
                "Input value is too deeply nested.",
                path=path,
            )
        )
    if value is None or isinstance(value, (bool, int, str)):
        return Result.ok(value)
    if isinstance(value, float):
        if not math.isfinite(value):
            return Result.err(
                _error(
                    "HUMAN_INPUT_VALUE_INVALID",
                    "Input value must be finite.",
                    path=path,
                )
            )
        return Result.ok(value)
    if isinstance(value, Mapping):
        if len(value) > _MAX_JSON_ITEMS:
            return Result.err(
                _error(
                    "HUMAN_INPUT_VALUE_TOO_LARGE",
                    "Input object has too many items.",
                    path=path,
                )
            )
        copied: Dict[str, Any] = {}
        for key, item in value.items():
            if not isinstance(key, str):
                return Result.err(
                    _error(
                        "HUMAN_INPUT_VALUE_INVALID",
                        "Input object keys must be strings.",
                        path=path,
                    )
                )
            child = _copy_json(item, path=f"{path}.{key}", depth=depth + 1)
            if child.is_err():
                return Result.err(child.unwrap_err())
            copied[key] = child.unwrap()
        return Result.ok(copied)
    if isinstance(value, (list, tuple)):
        if len(value) > _MAX_JSON_ITEMS:
            return Result.err(
                _error(
                    "HUMAN_INPUT_VALUE_TOO_LARGE",
                    "Input list has too many items.",
                    path=path,
                )
            )
        copied_list: List[Any] = []
        for index, item in enumerate(value):
            child = _copy_json(item, path=f"{path}[{index}]", depth=depth + 1)
            if child.is_err():
                return Result.err(child.unwrap_err())
            copied_list.append(child.unwrap())
        return Result.ok(copied_list)
    return Result.err(
        _error(
            "HUMAN_INPUT_VALUE_INVALID",
            "Input values must be JSON-compatible data.",
            path=path,
            value_type=type(value).__name__,
        )
    )


def _copy_bounded_json(value: Any) -> Result[Any, Error]:
    copied = _copy_json(value)
    if copied.is_err():
        return Result.err(copied.unwrap_err())
    try:
        encoded = json.dumps(copied.unwrap(), ensure_ascii=False, allow_nan=False)
    except (TypeError, ValueError) as exc:
        return Result.err(
            _error(
                "HUMAN_INPUT_VALUE_INVALID",
                "Input value is not JSON serializable.",
                reason=str(exc)[:256],
            )
        )
    if len(encoded.encode("utf-8")) > _MAX_RECORD_BYTES:
        return Result.err(
            _error(
                "HUMAN_INPUT_VALUE_TOO_LARGE",
                "Input value exceeds the configured byte limit.",
                max_bytes=_MAX_RECORD_BYTES,
            )
        )
    return Result.ok(copied.unwrap())


def _valid_identifier(value: Any, field_name: str) -> Optional[Error]:
    if not isinstance(value, str) or not _IDENTIFIER.fullmatch(value):
        return _error(
            "HUMAN_INPUT_IDENTIFIER_INVALID",
            f"{field_name} must contain 1-128 letters, numbers, '_', '.', ':', or '-'.",
            field=field_name,
        )
    return None


def _valid_prompt(value: Any) -> Optional[Error]:
    if not isinstance(value, str) or not value or len(value) > _MAX_PROMPT_LENGTH:
        return _error(
            "HUMAN_INPUT_PROMPT_INVALID",
            "prompt must be a non-empty string of at most 4096 characters.",
        )
    return None


def _valid_reason(value: Any) -> Optional[Error]:
    if not isinstance(value, str) or not value or len(value) > _MAX_REASON_LENGTH:
        return _error(
            "HUMAN_INPUT_REASON_INVALID",
            "rejection reason must be a non-empty string of at most 256 characters.",
        )
    return None


@dataclass(frozen=True)
class HumanInputDecision:
    """Immutable accepted or rejected response for one input request."""

    interaction_id: str
    accepted: bool
    decided_at: float
    response: Any = None
    rejection_reason: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "interaction_id": self.interaction_id,
            "accepted": self.accepted,
            "decided_at": self.decided_at,
            "response": self.response,
            "rejection_reason": self.rejection_reason,
        }


@dataclass(frozen=True)
class HumanInputRequest:
    """JSON-safe durable request awaiting one host response."""

    interaction_id: str
    run_id: str
    tool_call_id: str
    prompt: str
    input_schema: Dict[str, Any]
    status: str = "pending"
    created_at: float = 0.0
    updated_at: float = 0.0
    decision: Optional[HumanInputDecision] = None

    def __post_init__(self) -> None:
        now = time.time()
        if self.created_at == 0.0:
            object.__setattr__(self, "created_at", now)
        if self.updated_at == 0.0:
            object.__setattr__(self, "updated_at", now)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "interaction_id": self.interaction_id,
            "run_id": self.run_id,
            "tool_call_id": self.tool_call_id,
            "prompt": self.prompt,
            "input_schema": self.input_schema,
            "status": self.status,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "decision": self.decision.to_dict() if self.decision else None,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "HumanInputRequest":
        if not isinstance(data, Mapping):
            raise ValueError("human input request must be an object")
        required = (
            "interaction_id",
            "run_id",
            "tool_call_id",
            "prompt",
            "input_schema",
        )
        if any(field_name not in data for field_name in required):
            raise ValueError("human input request is missing a required field")
        for field_name in ("interaction_id", "run_id", "tool_call_id"):
            if _valid_identifier(data[field_name], field_name):
                raise ValueError(f"invalid {field_name}")
        if _valid_prompt(data["prompt"]):
            raise ValueError("invalid prompt")
        schema = _copy_bounded_json(data["input_schema"])
        if schema.is_err() or not isinstance(schema.unwrap(), dict):
            raise ValueError("input_schema must be a bounded JSON object")
        status = data.get("status", "pending")
        if status not in _STATUSES:
            raise ValueError("invalid human input status")
        decision_data = data.get("decision")
        decision: Optional[HumanInputDecision] = None
        if decision_data is not None:
            if not isinstance(decision_data, Mapping):
                raise ValueError("human input decision must be an object or null")
            if decision_data.get("interaction_id") != data["interaction_id"]:
                raise ValueError("human input decision ID does not match request")
            if type(decision_data.get("accepted")) is not bool:
                raise ValueError("human input decision must contain a boolean")
            decided_at = float(decision_data.get("decided_at", time.time()))
            if not math.isfinite(decided_at):
                raise ValueError("human input decision timestamp must be finite")
            rejection_reason = decision_data.get("rejection_reason")
            if rejection_reason is not None and _valid_reason(rejection_reason):
                raise ValueError("invalid rejection reason")
            response = _copy_bounded_json(decision_data.get("response"))
            if response.is_err():
                raise ValueError(response.unwrap_err()["message"])
            decision = HumanInputDecision(
                interaction_id=data["interaction_id"],
                accepted=decision_data["accepted"],
                decided_at=decided_at,
                response=response.unwrap(),
                rejection_reason=rejection_reason,
            )
        if status == "pending" and decision is not None:
            raise ValueError("pending human input cannot contain a decision")
        if status == "responded" and (decision is None or not decision.accepted):
            raise ValueError("responded human input must contain an accepted decision")
        if status == "rejected" and (decision is None or decision.accepted):
            raise ValueError("rejected human input must contain a rejected decision")
        if status == "consumed" and decision is None:
            raise ValueError("consumed human input must contain a decision")
        created_at = float(data.get("created_at", time.time()))
        updated_at = float(data.get("updated_at", time.time()))
        if not math.isfinite(created_at) or not math.isfinite(updated_at):
            raise ValueError("human input timestamps must be finite")
        return cls(
            interaction_id=data["interaction_id"],
            run_id=data["run_id"],
            tool_call_id=data["tool_call_id"],
            prompt=data["prompt"],
            input_schema=schema.unwrap(),
            status=status,
            created_at=created_at,
            updated_at=updated_at,
            decision=decision,
        )


class HumanInputStore(Protocol):
    """Persistence contract for bounded human request/response records."""

    def get(
        self, interaction_id: str
    ) -> Result[Optional[HumanInputRequest], Error]: ...

    def create(
        self, request: HumanInputRequest
    ) -> Result[HumanInputRequest, Error]: ...

    def respond(
        self, interaction_id: str, response: Any
    ) -> Result[HumanInputRequest, Error]: ...

    def reject(
        self, interaction_id: str, reason: str = "Operator rejected the request."
    ) -> Result[HumanInputRequest, Error]: ...

    def consume(self, interaction_id: str) -> Result[HumanInputRequest, Error]: ...

    def list_pending(
        self, limit: int = 100
    ) -> Result[List[HumanInputRequest], Error]: ...


def _copy_request(request: HumanInputRequest) -> HumanInputRequest:
    return HumanInputRequest.from_dict(request.to_dict())


def _validate_response(request: HumanInputRequest, response: Any) -> Result[Any, Error]:
    copied = _copy_bounded_json(response)
    if copied.is_err():
        return Result.err(copied.unwrap_err())
    try:
        validation = validate_json_schema(copied.unwrap(), request.input_schema)
    except (AttributeError, TypeError):
        return Result.err(
            _error(
                "HUMAN_INPUT_RESPONSE_INVALID",
                "The requested input schema is invalid.",
            )
        )
    if validation.is_err():
        return Result.err(
            _error(
                "HUMAN_INPUT_RESPONSE_INVALID",
                "Response does not satisfy the requested input schema.",
                reason=validation.unwrap_err().get(
                    "message", "schema validation failed"
                ),
            )
        )
    return Result.ok(copied.unwrap())


def _validate_limit(limit: int) -> Optional[Error]:
    if (
        not isinstance(limit, int)
        or isinstance(limit, bool)
        or not 0 < limit <= _MAX_LIST_LIMIT
    ):
        return _error(
            "HUMAN_INPUT_LIMIT_INVALID", "Human input list limit is out of bounds."
        )
    return None


class InMemoryHumanInputStore:
    """Thread-safe human-input store for local runs and tests."""

    def __init__(self) -> None:
        self._requests: Dict[str, HumanInputRequest] = {}
        self._lock = threading.RLock()

    def get(self, interaction_id: str) -> Result[Optional[HumanInputRequest], Error]:
        identifier_error = _valid_identifier(interaction_id, "interaction_id")
        if identifier_error:
            return Result.err(identifier_error)
        with self._lock:
            request = self._requests.get(interaction_id)
            return Result.ok(None if request is None else _copy_request(request))

    def create(self, request: HumanInputRequest) -> Result[HumanInputRequest, Error]:
        try:
            candidate = _copy_request(request)
        except (TypeError, ValueError) as exc:
            return Result.err(
                _error(
                    "HUMAN_INPUT_INVALID",
                    "Invalid human input request.",
                    reason=str(exc)[:256],
                )
            )
        if candidate.status != "pending" or candidate.decision is not None:
            return Result.err(
                _error(
                    "HUMAN_INPUT_INVALID", "New human input requests must be pending."
                )
            )
        with self._lock:
            existing = self._requests.get(candidate.interaction_id)
            if existing is not None:
                same_request = (
                    existing.run_id == candidate.run_id
                    and existing.tool_call_id == candidate.tool_call_id
                    and existing.prompt == candidate.prompt
                    and existing.input_schema == candidate.input_schema
                )
                if not same_request:
                    return Result.err(
                        _error(
                            "HUMAN_INPUT_CONFLICT",
                            "Interaction ID is already bound to another request.",
                        )
                    )
                return Result.ok(_copy_request(existing))
            self._requests[candidate.interaction_id] = candidate
            return Result.ok(_copy_request(candidate))

    def respond(
        self, interaction_id: str, response: Any
    ) -> Result[HumanInputRequest, Error]:
        return self._decide(interaction_id, accepted=True, response=response)

    def reject(
        self, interaction_id: str, reason: str = "Operator rejected the request."
    ) -> Result[HumanInputRequest, Error]:
        if _valid_reason(reason):
            return Result.err(
                _error("HUMAN_INPUT_REASON_INVALID", "Invalid rejection reason.")
            )
        return self._decide(
            interaction_id, accepted=False, response=None, reason=reason
        )

    def _decide(
        self,
        interaction_id: str,
        *,
        accepted: bool,
        response: Any,
        reason: Optional[str] = None,
    ) -> Result[HumanInputRequest, Error]:
        identifier_error = _valid_identifier(interaction_id, "interaction_id")
        if identifier_error:
            return Result.err(identifier_error)
        with self._lock:
            request = self._requests.get(interaction_id)
            if request is None:
                return Result.err(
                    _error(
                        "HUMAN_INPUT_NOT_FOUND", "Human input request was not found."
                    )
                )
            if request.status != "pending":
                return Result.err(
                    _error(
                        "HUMAN_INPUT_CONFLICT",
                        "Human input request already has a terminal state.",
                        status=request.status,
                    )
                )
            if accepted:
                response_result = _validate_response(request, response)
                if response_result.is_err():
                    return Result.err(response_result.unwrap_err())
                response = response_result.unwrap()
            decided_at = time.time()
            decision = HumanInputDecision(
                interaction_id, accepted, decided_at, response, reason
            )
            decided = replace(
                request,
                status="responded" if accepted else "rejected",
                updated_at=decided_at,
                decision=decision,
            )
            self._requests[interaction_id] = decided
            return Result.ok(_copy_request(decided))

    def consume(self, interaction_id: str) -> Result[HumanInputRequest, Error]:
        identifier_error = _valid_identifier(interaction_id, "interaction_id")
        if identifier_error:
            return Result.err(identifier_error)
        with self._lock:
            request = self._requests.get(interaction_id)
            if request is None:
                return Result.err(
                    _error(
                        "HUMAN_INPUT_NOT_FOUND", "Human input request was not found."
                    )
                )
            if request.status not in {"responded", "rejected"}:
                return Result.err(
                    _error(
                        "HUMAN_INPUT_NOT_READY",
                        "Only a decided human input request can be consumed.",
                        status=request.status,
                    )
                )
            consumed = replace(request, status="consumed", updated_at=time.time())
            self._requests[interaction_id] = consumed
            return Result.ok(_copy_request(consumed))

    def list_pending(self, limit: int = 100) -> Result[List[HumanInputRequest], Error]:
        limit_error = _validate_limit(limit)
        if limit_error:
            return Result.err(limit_error)
        with self._lock:
            pending = sorted(
                (
                    request
                    for request in self._requests.values()
                    if request.status == "pending"
                ),
                key=lambda request: (request.created_at, request.interaction_id),
            )
            return Result.ok([_copy_request(request) for request in pending[:limit]])


class FileHumanInputStore:
    """Atomic JSON-file human-input store for local process-restart handoff."""

    def __init__(
        self, directory: Union[str, Path], max_record_bytes: int = _MAX_RECORD_BYTES
    ) -> None:
        if (
            not isinstance(max_record_bytes, int)
            or isinstance(max_record_bytes, bool)
            or max_record_bytes <= 0
        ):
            raise ValueError("max_record_bytes must be a positive integer")
        self.directory = Path(directory).expanduser().resolve()
        self.directory.mkdir(parents=True, exist_ok=True)
        self.max_record_bytes = max_record_bytes
        self._lock = threading.RLock()

    def _path(self, interaction_id: str) -> Path:
        identifier_error = _valid_identifier(interaction_id, "interaction_id")
        if identifier_error:
            raise ValueError(identifier_error["message"])
        path = (self.directory / f"{interaction_id}.json").resolve()
        if self.directory not in path.parents:
            raise ValueError("human input path escapes the configured directory")
        return path

    def _read_unlocked(self, interaction_id: str) -> Optional[HumanInputRequest]:
        path = self._path(interaction_id)
        if not path.exists():
            return None
        if path.stat().st_size > self.max_record_bytes:
            raise ValueError("human input record exceeds configured size limit")
        with path.open("r", encoding="utf-8") as handle:
            return HumanInputRequest.from_dict(json.load(handle))

    def _write_unlocked(self, request: HumanInputRequest) -> HumanInputRequest:
        payload = json.dumps(
            request.to_dict(), ensure_ascii=False, allow_nan=False, indent=2
        )
        if len(payload.encode("utf-8")) > self.max_record_bytes:
            raise ValueError("human input record exceeds configured size limit")
        temporary_path: Optional[Path] = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                dir=str(self.directory),
                prefix=f".{request.interaction_id}.",
                suffix=".tmp",
                delete=False,
            ) as handle:
                temporary_path = Path(handle.name)
                handle.write(payload)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(str(temporary_path), str(self._path(request.interaction_id)))
            temporary_path = None
        finally:
            if temporary_path is not None:
                try:
                    temporary_path.unlink()
                except OSError:
                    pass
        return _copy_request(request)

    def get(self, interaction_id: str) -> Result[Optional[HumanInputRequest], Error]:
        try:
            with self._lock:
                request = self._read_unlocked(interaction_id)
                return Result.ok(None if request is None else _copy_request(request))
        except (OSError, TypeError, ValueError, json.JSONDecodeError) as exc:
            return Result.err(
                _error(
                    "HUMAN_INPUT_LOAD_ERROR",
                    "Failed to load human input request.",
                    reason=str(exc)[:256],
                )
            )

    def create(self, request: HumanInputRequest) -> Result[HumanInputRequest, Error]:
        try:
            candidate = _copy_request(request)
            if candidate.status != "pending" or candidate.decision is not None:
                return Result.err(
                    _error(
                        "HUMAN_INPUT_INVALID",
                        "New human input requests must be pending.",
                    )
                )
            with self._lock:
                existing = self._read_unlocked(candidate.interaction_id)
                if existing is not None:
                    same_request = (
                        existing.run_id == candidate.run_id
                        and existing.tool_call_id == candidate.tool_call_id
                        and existing.prompt == candidate.prompt
                        and existing.input_schema == candidate.input_schema
                    )
                    if not same_request:
                        return Result.err(
                            _error(
                                "HUMAN_INPUT_CONFLICT",
                                "Interaction ID is already bound to another request.",
                            )
                        )
                    return Result.ok(_copy_request(existing))
                return Result.ok(self._write_unlocked(candidate))
        except (OSError, TypeError, ValueError, json.JSONDecodeError) as exc:
            return Result.err(
                _error(
                    "HUMAN_INPUT_SAVE_ERROR",
                    "Failed to save human input request.",
                    reason=str(exc)[:256],
                )
            )

    def respond(
        self, interaction_id: str, response: Any
    ) -> Result[HumanInputRequest, Error]:
        return self._decide(interaction_id, accepted=True, response=response)

    def reject(
        self, interaction_id: str, reason: str = "Operator rejected the request."
    ) -> Result[HumanInputRequest, Error]:
        if _valid_reason(reason):
            return Result.err(
                _error("HUMAN_INPUT_REASON_INVALID", "Invalid rejection reason.")
            )
        return self._decide(
            interaction_id, accepted=False, response=None, reason=reason
        )

    def _decide(
        self,
        interaction_id: str,
        *,
        accepted: bool,
        response: Any,
        reason: Optional[str] = None,
    ) -> Result[HumanInputRequest, Error]:
        try:
            with self._lock:
                request = self._read_unlocked(interaction_id)
                if request is None:
                    return Result.err(
                        _error(
                            "HUMAN_INPUT_NOT_FOUND",
                            "Human input request was not found.",
                        )
                    )
                if request.status != "pending":
                    return Result.err(
                        _error(
                            "HUMAN_INPUT_CONFLICT",
                            "Human input request already has a terminal state.",
                            status=request.status,
                        )
                    )
                if accepted:
                    response_result = _validate_response(request, response)
                    if response_result.is_err():
                        return Result.err(response_result.unwrap_err())
                    response = response_result.unwrap()
                decided_at = time.time()
                decision = HumanInputDecision(
                    interaction_id, accepted, decided_at, response, reason
                )
                return Result.ok(
                    self._write_unlocked(
                        replace(
                            request,
                            status="responded" if accepted else "rejected",
                            updated_at=decided_at,
                            decision=decision,
                        )
                    )
                )
        except (OSError, TypeError, ValueError, json.JSONDecodeError) as exc:
            return Result.err(
                _error(
                    "HUMAN_INPUT_SAVE_ERROR",
                    "Failed to save human input decision.",
                    reason=str(exc)[:256],
                )
            )

    def consume(self, interaction_id: str) -> Result[HumanInputRequest, Error]:
        try:
            with self._lock:
                request = self._read_unlocked(interaction_id)
                if request is None:
                    return Result.err(
                        _error(
                            "HUMAN_INPUT_NOT_FOUND",
                            "Human input request was not found.",
                        )
                    )
                if request.status not in {"responded", "rejected"}:
                    return Result.err(
                        _error(
                            "HUMAN_INPUT_NOT_READY",
                            "Only a decided human input request can be consumed.",
                            status=request.status,
                        )
                    )
                return Result.ok(
                    self._write_unlocked(
                        replace(request, status="consumed", updated_at=time.time())
                    )
                )
        except (OSError, TypeError, ValueError, json.JSONDecodeError) as exc:
            return Result.err(
                _error(
                    "HUMAN_INPUT_SAVE_ERROR",
                    "Failed to consume human input request.",
                    reason=str(exc)[:256],
                )
            )

    def list_pending(self, limit: int = 100) -> Result[List[HumanInputRequest], Error]:
        limit_error = _validate_limit(limit)
        if limit_error:
            return Result.err(limit_error)
        try:
            with self._lock:
                paths = [
                    path for path in self.directory.iterdir() if path.suffix == ".json"
                ][:_MAX_LIST_SCAN]
                pending = []
                for path in paths:
                    request = self._read_unlocked(path.stem)
                    if request is not None and request.status == "pending":
                        pending.append(request)
                pending.sort(
                    key=lambda request: (request.created_at, request.interaction_id)
                )
                return Result.ok(
                    [_copy_request(request) for request in pending[:limit]]
                )
        except (OSError, TypeError, ValueError, json.JSONDecodeError) as exc:
            return Result.err(
                _error(
                    "HUMAN_INPUT_LOAD_ERROR",
                    "Failed to list human input requests.",
                    reason=str(exc)[:256],
                )
            )
