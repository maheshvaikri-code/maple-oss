"""Bounded durable request/response records for human-in-the-loop runs."""

from __future__ import annotations

import ipaddress
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
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit, urlunsplit
from urllib.request import Request, urlopen

from ..core.result import Result
from ..resources.lease import FileLeaseManager
from .contracts import validate_json_schema
from .durable_leases import DurableRecordLease
from .notification_outbox import (
    DEFAULT_MAX_NOTIFICATION_OUTBOX_BYTES,
    DEFAULT_MAX_NOTIFICATION_OUTBOX_RECORD_BYTES,
    DEFAULT_MAX_NOTIFICATION_OUTBOX_RECORDS,
    DEFAULT_NOTIFICATION_OUTBOX_DRAIN_LEASE_TTL_SECONDS,
    FileNotificationOutbox,
)

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
_MAX_ROUNDS = 8
_HUMAN_INPUT_LEASE_TTL_SECONDS = 30.0
_NOTIFICATION_EVENTS = frozenset({"created", "continued", "responded", "rejected"})
_MAX_NOTIFICATION_ENDPOINT_BYTES = 4_096
_DEFAULT_NOTIFICATION_TIMEOUT_SECONDS = 10.0
_MAX_NOTIFICATION_REQUEST_BYTES = 512 * 1024
_MAX_NOTIFICATION_RESPONSE_BYTES = 64 * 1024


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


def _valid_max_rounds(value: Any) -> Optional[Error]:
    if (
        not isinstance(value, int)
        or isinstance(value, bool)
        or not 1 <= value <= _MAX_ROUNDS
    ):
        return _error(
            "HUMAN_INPUT_ROUND_LIMIT_INVALID",
            f"max_rounds must be an integer from 1 to {_MAX_ROUNDS}.",
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

    @classmethod
    def from_dict(
        cls, data: Mapping[str, Any], interaction_id: str
    ) -> "HumanInputDecision":
        if not isinstance(data, Mapping):
            raise ValueError("human input decision must be an object")
        if data.get("interaction_id") != interaction_id:
            raise ValueError("human input decision ID does not match request")
        if type(data.get("accepted")) is not bool:
            raise ValueError("human input decision must contain a boolean")
        decided_at = float(data.get("decided_at", time.time()))
        if not math.isfinite(decided_at):
            raise ValueError("human input decision timestamp must be finite")
        rejection_reason = data.get("rejection_reason")
        if rejection_reason is not None and _valid_reason(rejection_reason):
            raise ValueError("invalid rejection reason")
        response = _copy_bounded_json(data.get("response"))
        if response.is_err():
            raise ValueError(response.unwrap_err()["message"])
        return cls(
            interaction_id=interaction_id,
            accepted=data["accepted"],
            decided_at=decided_at,
            response=response.unwrap(),
            rejection_reason=rejection_reason,
        )


@dataclass(frozen=True)
class HumanInputRound:
    """Immutable completed round retained for a multi-round interaction."""

    round_index: int
    prompt: str
    input_schema: Dict[str, Any]
    status: str
    decision: HumanInputDecision

    def to_dict(self) -> Dict[str, Any]:
        return {
            "round_index": self.round_index,
            "prompt": self.prompt,
            "input_schema": _copy_bounded_json(self.input_schema).unwrap(),
            "status": self.status,
            "decision": self.decision.to_dict(),
        }

    @classmethod
    def from_dict(
        cls, data: Mapping[str, Any], interaction_id: str
    ) -> "HumanInputRound":
        if not isinstance(data, Mapping):
            raise ValueError("human input round must be an object")
        round_index = data.get("round_index")
        if (
            not isinstance(round_index, int)
            or isinstance(round_index, bool)
            or round_index < 0
            or round_index >= _MAX_ROUNDS
        ):
            raise ValueError("invalid human input round index")
        if _valid_prompt(data.get("prompt")):
            raise ValueError("invalid human input round prompt")
        schema = _copy_bounded_json(data.get("input_schema"))
        if schema.is_err() or not isinstance(schema.unwrap(), dict):
            raise ValueError("human input round schema must be a bounded object")
        status = data.get("status")
        if status not in {"responded", "rejected", "consumed"}:
            raise ValueError("invalid human input round status")
        decision = cls._decision(data.get("decision"), interaction_id)
        if status == "responded" and not decision.accepted:
            raise ValueError("responded human input round must be accepted")
        if status == "rejected" and decision.accepted:
            raise ValueError("rejected human input round must be rejected")
        return cls(
            round_index=round_index,
            prompt=data["prompt"],
            input_schema=schema.unwrap(),
            status=status,
            decision=decision,
        )

    @staticmethod
    def _decision(data: Any, interaction_id: str) -> HumanInputDecision:
        if data is None:
            raise ValueError("human input round must contain a decision")
        return HumanInputDecision.from_dict(data, interaction_id)


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
    max_rounds: int = 1
    round_index: int = 0
    history: tuple[HumanInputRound, ...] = ()

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
            "max_rounds": self.max_rounds,
            "round_index": self.round_index,
            "history": [round_item.to_dict() for round_item in self.history],
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
        max_rounds = data.get("max_rounds", 1)
        if _valid_max_rounds(max_rounds):
            raise ValueError("invalid max_rounds")
        round_index = data.get("round_index", 0)
        if (
            not isinstance(round_index, int)
            or isinstance(round_index, bool)
            or not 0 <= round_index < max_rounds
        ):
            raise ValueError("invalid human input round index")
        raw_history = data.get("history", [])
        if not isinstance(raw_history, list) or len(raw_history) > _MAX_ROUNDS - 1:
            raise ValueError("invalid human input history")
        history = tuple(
            HumanInputRound.from_dict(item, data["interaction_id"])
            for item in raw_history
        )
        if len(history) != round_index:
            raise ValueError("human input history does not match round index")
        if any(item.round_index != index for index, item in enumerate(history)):
            raise ValueError("human input history is not ordered")
        decision_data = data.get("decision")
        decision: Optional[HumanInputDecision] = None
        if decision_data is not None:
            decision = HumanInputDecision.from_dict(
                decision_data, data["interaction_id"]
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
            max_rounds=max_rounds,
            round_index=round_index,
            history=history,
        )


@dataclass(frozen=True)
class HumanInputNotification:
    """Bounded host notification for a human-input lifecycle transition."""

    event_type: str
    interaction_id: str
    run_id: str
    tool_call_id: str
    prompt: str
    input_schema: Dict[str, Any]
    status: str
    created_at: float
    updated_at: float
    round_index: int
    max_rounds: int
    actor_id: Optional[str] = None

    @classmethod
    def from_request(
        cls,
        request: HumanInputRequest,
        event_type: str,
        *,
        actor_id: Optional[str] = None,
    ) -> "HumanInputNotification":
        if not isinstance(event_type, str) or event_type not in _NOTIFICATION_EVENTS:
            raise ValueError("human input notification event type is invalid")
        schema = _copy_bounded_json(request.input_schema)
        if schema.is_err() or not isinstance(schema.unwrap(), dict):
            raise ValueError("human input notification schema is invalid")
        return cls(
            event_type=event_type,
            interaction_id=request.interaction_id,
            run_id=request.run_id,
            tool_call_id=request.tool_call_id,
            prompt=request.prompt,
            input_schema=schema.unwrap(),
            status=request.status,
            created_at=request.created_at,
            updated_at=request.updated_at,
            round_index=request.round_index,
            max_rounds=request.max_rounds,
            actor_id=actor_id,
        )

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "HumanInputNotification":
        """Parse one bounded notification without accepting response data."""
        if not isinstance(data, Mapping):
            raise ValueError("human input notification must be an object")
        required = (
            "event_type",
            "interaction_id",
            "run_id",
            "tool_call_id",
            "prompt",
            "input_schema",
            "status",
            "created_at",
            "updated_at",
            "round_index",
            "max_rounds",
        )
        if any(field_name not in data for field_name in required):
            raise ValueError("human input notification is missing a required field")
        event_type = data["event_type"]
        if not isinstance(event_type, str) or event_type not in _NOTIFICATION_EVENTS:
            raise ValueError("invalid human input notification event type")
        for field_name in ("interaction_id", "run_id", "tool_call_id"):
            if _valid_identifier(data[field_name], field_name):
                raise ValueError(f"invalid {field_name}")
        if _valid_prompt(data["prompt"]):
            raise ValueError("invalid human input notification prompt")
        schema = _copy_bounded_json(data["input_schema"])
        if schema.is_err() or not isinstance(schema.unwrap(), dict):
            raise ValueError("human input notification schema must be an object")
        status = data["status"]
        if not isinstance(status, str) or status not in _STATUSES:
            raise ValueError("invalid human input notification status")
        expected_status = {
            "created": "pending",
            "continued": "pending",
            "responded": "responded",
            "rejected": "rejected",
        }[event_type]
        if status != expected_status:
            raise ValueError("human input notification event and status disagree")
        max_rounds = data["max_rounds"]
        if _valid_max_rounds(max_rounds):
            raise ValueError("invalid human input notification max_rounds")
        round_index = data["round_index"]
        if (
            not isinstance(round_index, int)
            or isinstance(round_index, bool)
            or not 0 <= round_index < max_rounds
        ):
            raise ValueError("invalid human input notification round_index")
        try:
            created_at = float(data["created_at"])
            updated_at = float(data["updated_at"])
        except (TypeError, ValueError, OverflowError) as exc:
            raise ValueError("human input notification timestamps are invalid") from exc
        if not math.isfinite(created_at) or not math.isfinite(updated_at):
            raise ValueError("human input notification timestamps must be finite")
        actor_id = data.get("actor_id")
        if actor_id is not None and _valid_identifier(actor_id, "actor_id"):
            raise ValueError("invalid human input notification actor_id")
        return cls(
            event_type=event_type,
            interaction_id=data["interaction_id"],
            run_id=data["run_id"],
            tool_call_id=data["tool_call_id"],
            prompt=data["prompt"],
            input_schema=schema.unwrap(),
            status=status,
            created_at=created_at,
            updated_at=updated_at,
            round_index=round_index,
            max_rounds=max_rounds,
            actor_id=actor_id,
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_type": self.event_type,
            "interaction_id": self.interaction_id,
            "run_id": self.run_id,
            "tool_call_id": self.tool_call_id,
            "prompt": self.prompt,
            "input_schema": _copy_bounded_json(self.input_schema).unwrap(),
            "status": self.status,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "round_index": self.round_index,
            "max_rounds": self.max_rounds,
            "actor_id": self.actor_id,
        }


class HumanInputNotifier(Protocol):
    """Host callback for bounded human-input lifecycle notifications."""

    def notify(self, notification: HumanInputNotification) -> Result[None, Error]: ...


class HttpHumanInputNotifier:
    """Make one bounded HTTP delivery attempt for each local notification.

    The endpoint is host-configured. Loopback HTTP is allowed for local
    composition; non-loopback endpoints require HTTPS. This class never
    retries, stores, or deduplicates notifications.
    """

    def __init__(
        self,
        endpoint: str,
        *,
        auth_token: Optional[str] = None,
        timeout_seconds: float = _DEFAULT_NOTIFICATION_TIMEOUT_SECONDS,
        max_request_bytes: int = _MAX_NOTIFICATION_REQUEST_BYTES,
        max_response_bytes: int = _MAX_NOTIFICATION_RESPONSE_BYTES,
    ) -> None:
        if not isinstance(endpoint, str) or not endpoint.strip():
            raise ValueError("endpoint must be a non-empty URL")
        if any(
            ord(character) < 0x20 or ord(character) == 0x7F for character in endpoint
        ):
            raise ValueError("endpoint must not contain control characters")
        parsed = urlsplit(endpoint.strip())
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("endpoint must use http or https and include a host")
        try:
            hostname = parsed.hostname
        except ValueError as exc:
            raise ValueError("endpoint host is invalid") from exc
        if not hostname:
            raise ValueError("endpoint must include a host")
        if parsed.username is not None or parsed.password is not None:
            raise ValueError("endpoint must not contain user information")
        if parsed.query or parsed.fragment:
            raise ValueError("endpoint must not contain a query or fragment")
        if auth_token is not None:
            if not isinstance(auth_token, str) or not auth_token.strip():
                raise ValueError("auth_token must be non-empty when provided")
            if any(
                ord(character) < 0x20 or ord(character) == 0x7F
                for character in auth_token
            ):
                raise ValueError("auth_token must not contain control characters")
        is_loopback = hostname.lower() == "localhost"
        if not is_loopback:
            try:
                is_loopback = ipaddress.ip_address(hostname).is_loopback
            except ValueError:
                is_loopback = False
        if parsed.scheme != "https" and not is_loopback:
            raise ValueError("non-loopback notification delivery requires https")
        normalized_endpoint = urlunsplit(
            (parsed.scheme, parsed.netloc, parsed.path, "", "")
        )
        if len(normalized_endpoint.encode("utf-8")) > _MAX_NOTIFICATION_ENDPOINT_BYTES:
            raise ValueError("endpoint URL is too large")
        if not isinstance(timeout_seconds, (int, float)) or isinstance(
            timeout_seconds, bool
        ):
            raise ValueError("timeout_seconds must be a finite positive number")
        try:
            normalized_timeout = float(timeout_seconds)
        except (TypeError, ValueError, OverflowError) as exc:
            raise ValueError(
                "timeout_seconds must be a finite positive number"
            ) from exc
        if not math.isfinite(normalized_timeout) or normalized_timeout <= 0:
            raise ValueError("timeout_seconds must be a finite positive number")
        for value, name, maximum in (
            (max_request_bytes, "max_request_bytes", _MAX_NOTIFICATION_REQUEST_BYTES),
            (
                max_response_bytes,
                "max_response_bytes",
                _MAX_NOTIFICATION_RESPONSE_BYTES,
            ),
        ):
            if (
                not isinstance(value, int)
                or isinstance(value, bool)
                or not 0 < value <= maximum
            ):
                raise ValueError(f"{name} must be between 1 and {maximum}")
        self.endpoint = normalized_endpoint
        self.auth_token = auth_token
        self.timeout_seconds = normalized_timeout
        self.max_request_bytes = max_request_bytes
        self.max_response_bytes = max_response_bytes

    def notify(self, notification: HumanInputNotification) -> Result[None, Error]:
        """POST one notification and require an explicit acceptance body."""
        if not isinstance(notification, HumanInputNotification):
            return Result.err(
                _error(
                    "HUMAN_INPUT_NOTIFICATION_INVALID",
                    "notification must be a HumanInputNotification.",
                )
            )
        try:
            encoded = json.dumps(
                {"notification": notification.to_dict()},
                ensure_ascii=False,
                allow_nan=False,
                separators=(",", ":"),
            ).encode("utf-8")
        except (TypeError, ValueError, OverflowError) as exc:
            return Result.err(
                _error(
                    "HUMAN_INPUT_NOTIFICATION_INVALID",
                    "notification is not JSON serializable.",
                    reason=type(exc).__name__,
                )
            )
        if len(encoded) > self.max_request_bytes:
            return Result.err(
                _error(
                    "HUMAN_INPUT_NOTIFICATION_TOO_LARGE",
                    "notification exceeds the configured request byte limit.",
                    max_bytes=self.max_request_bytes,
                )
            )
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
        }
        if self.auth_token is not None:
            headers["Authorization"] = f"Bearer {self.auth_token}"
        request = Request(self.endpoint, data=encoded, headers=headers, method="POST")
        try:
            with urlopen(request, timeout=self.timeout_seconds) as response:
                status = int(response.status)
                raw = response.read(self.max_response_bytes + 1)
        except HTTPError as exc:
            status = int(exc.code)
            exc.close()
            return Result.err(
                _error(
                    "HUMAN_INPUT_NOTIFICATION_HTTP_ERROR",
                    "remote notification endpoint returned an error.",
                    status=status,
                )
            )
        except (URLError, TimeoutError, OSError):
            return Result.err(
                _error(
                    "HUMAN_INPUT_NOTIFICATION_TRANSPORT_ERROR",
                    "remote notification endpoint could not be reached.",
                )
            )
        if len(raw) > self.max_response_bytes:
            return Result.err(
                _error(
                    "HUMAN_INPUT_NOTIFICATION_RESPONSE_TOO_LARGE",
                    "remote notification response exceeds the configured byte limit.",
                    max_bytes=self.max_response_bytes,
                )
            )
        if not 200 <= status < 300:
            return Result.err(
                _error(
                    "HUMAN_INPUT_NOTIFICATION_HTTP_ERROR",
                    "remote notification endpoint returned an error.",
                    status=status,
                )
            )
        try:
            decoded = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            return Result.err(
                _error(
                    "HUMAN_INPUT_NOTIFICATION_RESPONSE_INVALID",
                    "remote notification response is not valid JSON.",
                )
            )
        if not isinstance(decoded, dict) or decoded.get("accepted") is not True:
            return Result.err(
                _error(
                    "HUMAN_INPUT_NOTIFICATION_RESPONSE_INVALID",
                    "remote notification response did not acknowledge acceptance.",
                )
            )
        return Result.ok(None)


class FileHumanInputNotificationOutbox(FileNotificationOutbox[HumanInputNotification]):
    """Durably queue human-input notifications for explicit host draining."""

    def __init__(
        self,
        directory: Union[str, Path],
        *,
        target: HumanInputNotifier,
        max_record_bytes: int = DEFAULT_MAX_NOTIFICATION_OUTBOX_RECORD_BYTES,
        max_records: int = DEFAULT_MAX_NOTIFICATION_OUTBOX_RECORDS,
        max_queue_bytes: int = DEFAULT_MAX_NOTIFICATION_OUTBOX_BYTES,
        lease_manager: Optional[FileLeaseManager] = None,
        lease_ttl_seconds: float = DEFAULT_NOTIFICATION_OUTBOX_DRAIN_LEASE_TTL_SECONDS,
    ) -> None:
        super().__init__(
            directory,
            target=target,
            notification_type=HumanInputNotification,
            encoder=lambda notification: notification.to_dict(),
            decoder=HumanInputNotification.from_dict,
            max_record_bytes=max_record_bytes,
            max_records=max_records,
            max_queue_bytes=max_queue_bytes,
            lease_manager=lease_manager,
            lease_ttl_seconds=lease_ttl_seconds,
        )


class HumanInputAuthorizer(Protocol):
    """Host callback for fail-closed human-input mutation authorization."""

    def authorize(
        self,
        actor_id: str,
        action: str,
        request: HumanInputRequest,
    ) -> Result[bool, Error]: ...


def _authorize_host(
    authorizer: Optional[HumanInputAuthorizer],
    actor_id: Optional[str],
    action: str,
    request: HumanInputRequest,
) -> Result[None, Error]:
    if authorizer is None:
        return Result.ok(None)
    if actor_id is None:
        return Result.err(
            _error(
                "HUMAN_INPUT_ACTOR_REQUIRED",
                "An actor_id is required when human input authorization is configured.",
            )
        )
    actor_error = _valid_identifier(actor_id, "actor_id")
    if actor_error:
        return Result.err(_error("HUMAN_INPUT_ACTOR_INVALID", actor_error["message"]))
    try:
        decision = authorizer.authorize(actor_id, action, _copy_request(request))
    except Exception as exc:
        return Result.err(
            _error(
                "HUMAN_INPUT_AUTHORIZATION_ERROR",
                "Human input authorization failed closed.",
                reason=str(exc)[:256],
            )
        )
    if not isinstance(decision, Result):
        return Result.err(
            _error(
                "HUMAN_INPUT_AUTHORIZATION_ERROR",
                "Human input authorizer returned an invalid result.",
            )
        )
    if decision.is_err():
        return Result.err(
            _error(
                "HUMAN_INPUT_AUTHORIZATION_ERROR",
                "Human input authorization failed closed.",
                reason=(
                    decision.unwrap_err().get("errorType", "unknown")
                    if isinstance(decision.unwrap_err(), dict)
                    else "unknown"
                ),
            )
        )
    if decision.unwrap() is not True:
        return Result.err(
            _error(
                "HUMAN_INPUT_UNAUTHORIZED",
                "Actor is not authorized for this human input action.",
                action=action,
            )
        )
    return Result.ok(None)


def _notify_host(
    notifier: Optional[HumanInputNotifier],
    request: HumanInputRequest,
    event_type: str,
    *,
    actor_id: Optional[str] = None,
) -> Result[None, Error]:
    if notifier is None:
        return Result.ok(None)
    try:
        notification = HumanInputNotification.from_request(
            request, event_type, actor_id=actor_id
        )
        delivered = notifier.notify(notification)
    except Exception as exc:
        return Result.err(
            _error(
                "HUMAN_INPUT_NOTIFICATION_ERROR",
                "Human input notification failed after persistence.",
                event_type=event_type,
                reason=str(exc)[:256],
            )
        )
    if not isinstance(delivered, Result) or delivered.is_err():
        reason = "invalid_result"
        if isinstance(delivered, Result) and isinstance(delivered.unwrap_err(), dict):
            reason = str(delivered.unwrap_err().get("errorType", "unknown"))[:64]
        return Result.err(
            _error(
                "HUMAN_INPUT_NOTIFICATION_ERROR",
                "Human input notification failed after persistence.",
                event_type=event_type,
                reason=reason,
            )
        )
    return Result.ok(None)


class HumanInputStore(Protocol):
    """Persistence contract for bounded human request/response records."""

    def get(
        self, interaction_id: str
    ) -> Result[Optional[HumanInputRequest], Error]: ...

    def create(
        self, request: HumanInputRequest
    ) -> Result[HumanInputRequest, Error]: ...

    def respond(
        self, interaction_id: str, response: Any, *, actor_id: Optional[str] = None
    ) -> Result[HumanInputRequest, Error]: ...

    def reject(
        self,
        interaction_id: str,
        reason: str = "Operator rejected the request.",
        *,
        actor_id: Optional[str] = None,
    ) -> Result[HumanInputRequest, Error]: ...

    def continue_round(
        self,
        interaction_id: str,
        prompt: str,
        input_schema: Mapping[str, Any],
        *,
        actor_id: Optional[str] = None,
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


def _continue_request(
    request: HumanInputRequest,
    prompt: Any,
    input_schema: Any,
) -> Result[HumanInputRequest, Error]:
    if request.status not in {"responded", "rejected", "consumed"}:
        return Result.err(
            _error(
                "HUMAN_INPUT_ROUND_CONFLICT",
                "Only a decided human input request can continue to another round.",
                status=request.status,
            )
        )
    next_round = request.round_index + 1
    if next_round >= request.max_rounds:
        return Result.err(
            _error(
                "HUMAN_INPUT_ROUND_LIMIT",
                "The human input interaction has reached its maximum round count.",
                max_rounds=request.max_rounds,
            )
        )
    prompt_error = _valid_prompt(prompt)
    if prompt_error:
        return Result.err(prompt_error)
    schema = _copy_bounded_json(input_schema)
    if schema.is_err() or not isinstance(schema.unwrap(), dict):
        return Result.err(
            _error(
                "HUMAN_INPUT_SCHEMA_INVALID",
                "The next human input schema must be a bounded JSON object.",
            )
        )
    if request.decision is None:
        return Result.err(
            _error(
                "HUMAN_INPUT_ROUND_CONFLICT",
                "A completed human input round must contain a decision.",
            )
        )
    history_item = HumanInputRound(
        round_index=request.round_index,
        prompt=request.prompt,
        input_schema=_copy_bounded_json(request.input_schema).unwrap(),
        status=request.status,
        decision=request.decision,
    )
    now = time.time()
    return Result.ok(
        replace(
            request,
            prompt=prompt,
            input_schema=schema.unwrap(),
            status="pending",
            updated_at=now,
            decision=None,
            round_index=next_round,
            history=request.history + (history_item,),
        )
    )


class InMemoryHumanInputStore:
    """Thread-safe human-input store for local runs and tests."""

    def __init__(
        self,
        *,
        notifier: Optional[HumanInputNotifier] = None,
        authorizer: Optional[HumanInputAuthorizer] = None,
    ) -> None:
        self._requests: Dict[str, HumanInputRequest] = {}
        self._lock = threading.RLock()
        self._notifier = notifier
        self._authorizer = authorizer
        if notifier is not None and not callable(getattr(notifier, "notify", None)):
            raise TypeError("human input notifier must implement notify")
        if authorizer is not None and not callable(
            getattr(authorizer, "authorize", None)
        ):
            raise TypeError("human input authorizer must implement authorize")

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
                    and existing.max_rounds == candidate.max_rounds
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
            notified = _notify_host(self._notifier, candidate, "created")
            if notified.is_err():
                return Result.err(notified.unwrap_err())
            return Result.ok(_copy_request(candidate))

    def respond(
        self,
        interaction_id: str,
        response: Any,
        *,
        actor_id: Optional[str] = None,
    ) -> Result[HumanInputRequest, Error]:
        return self._decide(
            interaction_id, accepted=True, response=response, actor_id=actor_id
        )

    def reject(
        self,
        interaction_id: str,
        reason: str = "Operator rejected the request.",
        *,
        actor_id: Optional[str] = None,
    ) -> Result[HumanInputRequest, Error]:
        if _valid_reason(reason):
            return Result.err(
                _error("HUMAN_INPUT_REASON_INVALID", "Invalid rejection reason.")
            )
        return self._decide(
            interaction_id,
            accepted=False,
            response=None,
            reason=reason,
            actor_id=actor_id,
        )

    def continue_round(
        self,
        interaction_id: str,
        prompt: str,
        input_schema: Mapping[str, Any],
        *,
        actor_id: Optional[str] = None,
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
            authorized = _authorize_host(
                self._authorizer, actor_id, "continue", request
            )
            if authorized.is_err():
                return Result.err(authorized.unwrap_err())
            continued = _continue_request(request, prompt, input_schema)
            if continued.is_err():
                return Result.err(continued.unwrap_err())
            next_request = continued.unwrap()
            self._requests[interaction_id] = next_request
            notified = _notify_host(
                self._notifier, next_request, "continued", actor_id=actor_id
            )
            if notified.is_err():
                return Result.err(notified.unwrap_err())
            return Result.ok(_copy_request(next_request))

    def _decide(
        self,
        interaction_id: str,
        *,
        accepted: bool,
        response: Any,
        reason: Optional[str] = None,
        actor_id: Optional[str] = None,
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
            authorized = _authorize_host(
                self._authorizer, actor_id, "respond" if accepted else "reject", request
            )
            if authorized.is_err():
                return Result.err(authorized.unwrap_err())
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
            notified = _notify_host(
                self._notifier,
                decided,
                "responded" if accepted else "rejected",
                actor_id=actor_id,
            )
            if notified.is_err():
                return Result.err(notified.unwrap_err())
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
    """Atomic JSON-file human-input store with per-record fencing leases."""

    def __init__(
        self,
        directory: Union[str, Path],
        max_record_bytes: int = _MAX_RECORD_BYTES,
        *,
        lease_manager: Optional[FileLeaseManager] = None,
        lease_ttl_seconds: float = _HUMAN_INPUT_LEASE_TTL_SECONDS,
        notifier: Optional[HumanInputNotifier] = None,
        authorizer: Optional[HumanInputAuthorizer] = None,
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
        self._notifier = notifier
        self._authorizer = authorizer
        if notifier is not None and not callable(getattr(notifier, "notify", None)):
            raise TypeError("human input notifier must implement notify")
        if authorizer is not None and not callable(
            getattr(authorizer, "authorize", None)
        ):
            raise TypeError("human input authorizer must implement authorize")
        self._record_leases = DurableRecordLease(
            self.directory,
            namespace="human-input",
            holder_label="human-input",
            lease_manager=lease_manager,
            lease_ttl_seconds=lease_ttl_seconds,
        )

    def _with_record_lease(
        self,
        interaction_id: str,
        operation: str,
        callback: Callable[[], Result[Any, Error]],
    ) -> Result[Any, Error]:
        return self._record_leases.run(
            interaction_id,
            operation,
            callback,
            acquire_error_type="HUMAN_INPUT_LEASE_ERROR",
            acquire_error_message="Human input record lease is unavailable.",
            release_error_type="HUMAN_INPUT_LEASE_RELEASE_ERROR",
            release_error_message="Human input record lease could not be released safely.",
        )

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
        return self._with_record_lease(
            interaction_id,
            "get",
            lambda: self._get_without_lease(interaction_id),
        )

    def _get_without_lease(
        self, interaction_id: str
    ) -> Result[Optional[HumanInputRequest], Error]:
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
        return self._with_record_lease(
            request.interaction_id,
            "create",
            lambda: self._create_without_lease(request),
        )

    def _create_without_lease(
        self, request: HumanInputRequest
    ) -> Result[HumanInputRequest, Error]:
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
                        and existing.max_rounds == candidate.max_rounds
                    )
                    if not same_request:
                        return Result.err(
                            _error(
                                "HUMAN_INPUT_CONFLICT",
                                "Interaction ID is already bound to another request.",
                            )
                        )
                    return Result.ok(_copy_request(existing))
                stored = self._write_unlocked(candidate)
                notified = _notify_host(self._notifier, stored, "created")
                if notified.is_err():
                    return Result.err(notified.unwrap_err())
                return Result.ok(stored)
        except (OSError, TypeError, ValueError, json.JSONDecodeError) as exc:
            return Result.err(
                _error(
                    "HUMAN_INPUT_SAVE_ERROR",
                    "Failed to save human input request.",
                    reason=str(exc)[:256],
                )
            )

    def respond(
        self,
        interaction_id: str,
        response: Any,
        *,
        actor_id: Optional[str] = None,
    ) -> Result[HumanInputRequest, Error]:
        return self._decide(
            interaction_id, accepted=True, response=response, actor_id=actor_id
        )

    def reject(
        self,
        interaction_id: str,
        reason: str = "Operator rejected the request.",
        *,
        actor_id: Optional[str] = None,
    ) -> Result[HumanInputRequest, Error]:
        if _valid_reason(reason):
            return Result.err(
                _error("HUMAN_INPUT_REASON_INVALID", "Invalid rejection reason.")
            )
        return self._decide(
            interaction_id,
            accepted=False,
            response=None,
            reason=reason,
            actor_id=actor_id,
        )

    def continue_round(
        self,
        interaction_id: str,
        prompt: str,
        input_schema: Mapping[str, Any],
        *,
        actor_id: Optional[str] = None,
    ) -> Result[HumanInputRequest, Error]:
        return self._with_record_lease(
            interaction_id,
            "continue",
            lambda: self._continue_round_without_lease(
                interaction_id, prompt, input_schema, actor_id=actor_id
            ),
        )

    def _continue_round_without_lease(
        self,
        interaction_id: str,
        prompt: str,
        input_schema: Mapping[str, Any],
        *,
        actor_id: Optional[str] = None,
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
                authorized = _authorize_host(
                    self._authorizer, actor_id, "continue", request
                )
                if authorized.is_err():
                    return Result.err(authorized.unwrap_err())
                continued = _continue_request(request, prompt, input_schema)
                if continued.is_err():
                    return Result.err(continued.unwrap_err())
                next_request = self._write_unlocked(continued.unwrap())
                notified = _notify_host(
                    self._notifier, next_request, "continued", actor_id=actor_id
                )
                if notified.is_err():
                    return Result.err(notified.unwrap_err())
                return Result.ok(next_request)
        except (OSError, TypeError, ValueError, json.JSONDecodeError) as exc:
            return Result.err(
                _error(
                    "HUMAN_INPUT_SAVE_ERROR",
                    "Failed to save the next human input round.",
                    reason=str(exc)[:256],
                )
            )

    def _decide(
        self,
        interaction_id: str,
        *,
        accepted: bool,
        response: Any,
        reason: Optional[str] = None,
        actor_id: Optional[str] = None,
    ) -> Result[HumanInputRequest, Error]:
        return self._with_record_lease(
            interaction_id,
            "respond" if accepted else "reject",
            lambda: self._decide_without_lease(
                interaction_id,
                accepted=accepted,
                response=response,
                reason=reason,
                actor_id=actor_id,
            ),
        )

    def _decide_without_lease(
        self,
        interaction_id: str,
        *,
        accepted: bool,
        response: Any,
        reason: Optional[str] = None,
        actor_id: Optional[str] = None,
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
                authorized = _authorize_host(
                    self._authorizer,
                    actor_id,
                    "respond" if accepted else "reject",
                    request,
                )
                if authorized.is_err():
                    return Result.err(authorized.unwrap_err())
                if accepted:
                    response_result = _validate_response(request, response)
                    if response_result.is_err():
                        return Result.err(response_result.unwrap_err())
                    response = response_result.unwrap()
                decided_at = time.time()
                decision = HumanInputDecision(
                    interaction_id, accepted, decided_at, response, reason
                )
                decided = self._write_unlocked(
                    replace(
                        request,
                        status="responded" if accepted else "rejected",
                        updated_at=decided_at,
                        decision=decision,
                    )
                )
                notified = _notify_host(
                    self._notifier,
                    decided,
                    "responded" if accepted else "rejected",
                    actor_id=actor_id,
                )
                if notified.is_err():
                    return Result.err(notified.unwrap_err())
                return Result.ok(decided)
        except (OSError, TypeError, ValueError, json.JSONDecodeError) as exc:
            return Result.err(
                _error(
                    "HUMAN_INPUT_SAVE_ERROR",
                    "Failed to save human input decision.",
                    reason=str(exc)[:256],
                )
            )

    def consume(self, interaction_id: str) -> Result[HumanInputRequest, Error]:
        return self._with_record_lease(
            interaction_id,
            "consume",
            lambda: self._consume_without_lease(interaction_id),
        )

    def _consume_without_lease(
        self, interaction_id: str
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
        return self._with_record_lease(
            "__list__",
            "list_pending",
            lambda: self._list_pending_without_lease(limit),
        )

    def _list_pending_without_lease(
        self, limit: int = 100
    ) -> Result[List[HumanInputRequest], Error]:
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
