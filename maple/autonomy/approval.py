"""Durable, fail-closed approval records for autonomous tool actions."""

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
from .durable_leases import DurableRecordLease

_IDENTIFIER = re.compile(r"^[A-Za-z0-9_.:-]{1,128}$")
_STATUSES = {"pending", "approved", "denied", "consumed"}
_MAX_ARGUMENT_BYTES = 65_536
_MAX_ARGUMENT_DEPTH = 16
_MAX_ARGUMENT_ITEMS = 1_000
_MAX_LIST_LIMIT = 1_000
_MAX_LIST_SCAN = 10_000
_MAX_EXECUTION_RESULT_BYTES = 131_072
_APPROVAL_LEASE_TTL_SECONDS = 30.0
_APPROVAL_NOTIFICATION_EVENTS = frozenset({"created", "approved", "denied"})
_MAX_NOTIFICATION_ENDPOINT_BYTES = 4_096
_DEFAULT_NOTIFICATION_TIMEOUT_SECONDS = 10.0
_MAX_NOTIFICATION_REQUEST_BYTES = 512 * 1024
_MAX_NOTIFICATION_RESPONSE_BYTES = 64 * 1024

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


def _copy_execution_result(value: Any) -> Result[Optional[Dict[str, Any]], Error]:
    """Validate one bounded terminal tool outcome for durable replay."""
    if value is None:
        return Result.ok(None)
    if not isinstance(value, Mapping):
        return Result.err(
            _error(
                "APPROVAL_EXECUTION_INVALID",
                "Approval execution outcome must be an object.",
            )
        )
    content = value.get("content")
    is_error = value.get("is_error")
    if not isinstance(content, str) or type(is_error) is not bool:
        return Result.err(
            _error(
                "APPROVAL_EXECUTION_INVALID",
                "Approval execution outcome has invalid fields.",
            )
        )
    if len(content.encode("utf-8")) > _MAX_EXECUTION_RESULT_BYTES:
        return Result.err(
            _error(
                "APPROVAL_EXECUTION_TOO_LARGE",
                "Approval execution outcome exceeds the configured byte limit.",
                max_bytes=_MAX_EXECUTION_RESULT_BYTES,
            )
        )
    normalized = {"content": content, "is_error": is_error}
    try:
        encoded = json.dumps(normalized, ensure_ascii=False, allow_nan=False)
        json.loads(encoded)
    except (TypeError, ValueError, json.JSONDecodeError) as exc:
        return Result.err(
            _error(
                "APPROVAL_EXECUTION_INVALID",
                "Approval execution outcome is not JSON serializable.",
                reason=str(exc)[:256],
            )
        )
    return Result.ok(normalized)


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


def _valid_correlation_id(value: Any, field_name: str) -> Optional[Error]:
    if value is None:
        return None
    if (
        not isinstance(value, str)
        or not value
        or len(value) > 128
        or any(ord(char) < 32 or ord(char) == 127 for char in value)
    ):
        return _error(
            "INVALID_APPROVAL_CORRELATION",
            f"{field_name} must be a bounded string without control characters.",
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
    execution_result: Optional[Dict[str, Any]] = None
    trace_id: Optional[str] = None
    span_id: Optional[str] = None

    def __post_init__(self) -> None:
        now = time.time()
        if self.created_at == 0.0:
            object.__setattr__(self, "created_at", now)
        if self.updated_at == 0.0:
            object.__setattr__(self, "updated_at", now)
        normalized = _copy_execution_result(self.execution_result)
        if normalized.is_err():
            raise ValueError(normalized.unwrap_err()["message"])
        if self.execution_result is not None and self.status != "consumed":
            raise ValueError("only consumed approvals can contain an execution result")
        object.__setattr__(self, "execution_result", normalized.unwrap())
        for field_name, value in (
            ("trace_id", self.trace_id),
            ("span_id", self.span_id),
        ):
            if _valid_correlation_id(value, field_name):
                raise ValueError(f"invalid {field_name}")

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
            "execution_result": (
                dict(self.execution_result)
                if self.execution_result is not None
                else None
            ),
            "trace_id": self.trace_id,
            "span_id": self.span_id,
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
        execution_result = _copy_execution_result(data.get("execution_result"))
        if execution_result.is_err():
            raise ValueError(execution_result.unwrap_err()["message"])
        if status == "pending" and decision is not None:
            raise ValueError("pending approval cannot contain a decision")
        if status in {"approved", "consumed"} and (
            decision is None or not decision.approved
        ):
            raise ValueError("approved approval must contain an approving decision")
        if status == "denied" and (decision is None or decision.approved):
            raise ValueError("denied approval must contain a denying decision")
        if execution_result.unwrap() is not None and status != "consumed":
            raise ValueError("only consumed approvals can contain an execution result")
        created_at = float(data.get("created_at", time.time()))
        updated_at = float(data.get("updated_at", time.time()))
        if not math.isfinite(created_at) or not math.isfinite(updated_at):
            raise ValueError("approval timestamps must be finite")
        for field_name in ("trace_id", "span_id"):
            if _valid_correlation_id(data.get(field_name), field_name):
                raise ValueError(f"invalid {field_name}")
        return cls(
            approval_id=data["approval_id"],
            tool_call_id=data["tool_call_id"],
            tool_name=data["tool_name"],
            arguments=arguments.unwrap(),
            status=status,
            created_at=created_at,
            updated_at=updated_at,
            decision=decision,
            execution_result=execution_result.unwrap(),
            trace_id=data.get("trace_id"),
            span_id=data.get("span_id"),
        )


@dataclass(frozen=True)
class ApprovalNotification:
    """Bounded host notification for an approval lifecycle transition."""

    event_type: str
    approval_id: str
    tool_call_id: str
    tool_name: str
    arguments: Dict[str, Any]
    status: str
    created_at: float
    updated_at: float
    decision: Optional[ApprovalDecision] = None
    trace_id: Optional[str] = None
    span_id: Optional[str] = None

    @classmethod
    def from_request(
        cls, request: ApprovalRequest, event_type: str
    ) -> "ApprovalNotification":
        if (
            not isinstance(event_type, str)
            or event_type not in _APPROVAL_NOTIFICATION_EVENTS
        ):
            raise ValueError("approval notification event type is invalid")
        expected_status = {
            "created": "pending",
            "approved": "approved",
            "denied": "denied",
        }[event_type]
        if request.status != expected_status:
            raise ValueError("approval notification event and status disagree")
        arguments = _copy_arguments(request.arguments)
        if arguments.is_err():
            raise ValueError(arguments.unwrap_err()["message"])
        return cls(
            event_type=event_type,
            approval_id=request.approval_id,
            tool_call_id=request.tool_call_id,
            tool_name=request.tool_name,
            arguments=arguments.unwrap(),
            status=request.status,
            created_at=request.created_at,
            updated_at=request.updated_at,
            decision=request.decision,
            trace_id=request.trace_id,
            span_id=request.span_id,
        )

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "ApprovalNotification":
        """Parse one notification without accepting execution outcomes."""
        if not isinstance(data, Mapping):
            raise ValueError("approval notification must be an object")
        required = (
            "event_type",
            "approval_id",
            "tool_call_id",
            "tool_name",
            "arguments",
            "status",
            "created_at",
            "updated_at",
            "decision",
        )
        if any(field_name not in data for field_name in required):
            raise ValueError("approval notification is missing a required field")
        event_type = data["event_type"]
        if (
            not isinstance(event_type, str)
            or event_type not in _APPROVAL_NOTIFICATION_EVENTS
        ):
            raise ValueError("invalid approval notification event type")
        for field_name in ("approval_id", "tool_call_id"):
            if _valid_identifier(data[field_name], field_name):
                raise ValueError(f"invalid {field_name}")
        if _valid_text(data["tool_name"], "tool_name"):
            raise ValueError("invalid tool_name")
        arguments = _copy_arguments(data["arguments"])
        if arguments.is_err():
            raise ValueError(arguments.unwrap_err()["message"])
        status = data["status"]
        if not isinstance(status, str) or status not in _STATUSES:
            raise ValueError("invalid approval notification status")
        expected_status = {
            "created": "pending",
            "approved": "approved",
            "denied": "denied",
        }[event_type]
        if status != expected_status:
            raise ValueError("approval notification event and status disagree")
        decision_data = data["decision"]
        decision: Optional[ApprovalDecision] = None
        if decision_data is not None:
            if not isinstance(decision_data, Mapping):
                raise ValueError("approval notification decision must be an object")
            if decision_data.get("approval_id") != data["approval_id"]:
                raise ValueError("approval notification decision ID does not match")
            approved = decision_data.get("approved")
            expected_approved = event_type == "approved"
            if type(approved) is not bool or approved != expected_approved:
                raise ValueError("approval notification decision is invalid")
            if "decided_at" not in decision_data:
                raise ValueError("approval notification decision is invalid")
            try:
                decided_at = float(decision_data["decided_at"])
            except (TypeError, ValueError, OverflowError) as exc:
                raise ValueError("approval notification decision is invalid") from exc
            edited_arguments_data = decision_data.get("edited_arguments")
            edited_arguments: Optional[Dict[str, Any]] = None
            if edited_arguments_data is not None:
                edited = _copy_arguments(edited_arguments_data)
                if edited.is_err():
                    raise ValueError(edited.unwrap_err()["message"])
                edited_arguments = edited.unwrap()
            try:
                decision = ApprovalDecision(
                    approval_id=data["approval_id"],
                    approved=approved,
                    decided_at=decided_at,
                    edited_arguments=edited_arguments,
                )
            except (TypeError, ValueError) as exc:
                raise ValueError("approval notification decision is invalid") from exc
        if event_type == "created" and decision is not None:
            raise ValueError("created approval notification cannot contain a decision")
        if event_type != "created" and decision is None:
            raise ValueError("decided approval notification requires a decision")
        try:
            created_at = float(data["created_at"])
            updated_at = float(data["updated_at"])
        except (TypeError, ValueError, OverflowError) as exc:
            raise ValueError("approval notification timestamps are invalid") from exc
        if not math.isfinite(created_at) or not math.isfinite(updated_at):
            raise ValueError("approval notification timestamps must be finite")
        for field_name in ("trace_id", "span_id"):
            if _valid_correlation_id(data.get(field_name), field_name):
                raise ValueError(f"invalid {field_name}")
        return cls(
            event_type=event_type,
            approval_id=data["approval_id"],
            tool_call_id=data["tool_call_id"],
            tool_name=data["tool_name"],
            arguments=arguments.unwrap(),
            status=status,
            created_at=created_at,
            updated_at=updated_at,
            decision=decision,
            trace_id=data.get("trace_id"),
            span_id=data.get("span_id"),
        )

    def to_dict(self) -> Dict[str, Any]:
        arguments = _copy_arguments(self.arguments)
        if arguments.is_err():
            raise ValueError(arguments.unwrap_err()["message"])
        return {
            "event_type": self.event_type,
            "approval_id": self.approval_id,
            "tool_call_id": self.tool_call_id,
            "tool_name": self.tool_name,
            "arguments": arguments.unwrap(),
            "status": self.status,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "decision": self.decision.to_dict() if self.decision else None,
            "trace_id": self.trace_id,
            "span_id": self.span_id,
        }


class ApprovalNotifier(Protocol):
    """Host callback for bounded approval lifecycle notifications."""

    def notify(self, notification: ApprovalNotification) -> Result[None, Error]: ...


def _notify_host(
    notifier: Optional[ApprovalNotifier],
    request: ApprovalRequest,
    event_type: str,
) -> Result[None, Error]:
    if notifier is None:
        return Result.ok(None)
    try:
        notification = ApprovalNotification.from_request(request, event_type)
        delivered = notifier.notify(notification)
    except Exception as exc:
        return Result.err(
            _error(
                "APPROVAL_NOTIFICATION_ERROR",
                "Approval notification failed after persistence.",
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
                "APPROVAL_NOTIFICATION_ERROR",
                "Approval notification failed after persistence.",
                event_type=event_type,
                reason=reason,
            )
        )
    return Result.ok(None)


class HttpApprovalNotifier:
    """Make one bounded HTTP delivery attempt for each approval notification."""

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

    def notify(self, notification: ApprovalNotification) -> Result[None, Error]:
        """POST one notification and require an explicit acceptance body."""
        if not isinstance(notification, ApprovalNotification):
            return Result.err(
                _error(
                    "APPROVAL_NOTIFICATION_INVALID",
                    "notification must be an ApprovalNotification.",
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
                    "APPROVAL_NOTIFICATION_INVALID",
                    "notification is not JSON serializable.",
                    reason=type(exc).__name__,
                )
            )
        if len(encoded) > self.max_request_bytes:
            return Result.err(
                _error(
                    "APPROVAL_NOTIFICATION_TOO_LARGE",
                    "notification exceeds the configured request byte limit.",
                    max_bytes=self.max_request_bytes,
                )
            )
        headers = {"Accept": "application/json", "Content-Type": "application/json"}
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
                    "APPROVAL_NOTIFICATION_HTTP_ERROR",
                    "remote approval notification endpoint returned an error.",
                    status=status,
                )
            )
        except (URLError, TimeoutError, OSError):
            return Result.err(
                _error(
                    "APPROVAL_NOTIFICATION_TRANSPORT_ERROR",
                    "remote approval notification endpoint could not be reached.",
                )
            )
        if len(raw) > self.max_response_bytes:
            return Result.err(
                _error(
                    "APPROVAL_NOTIFICATION_RESPONSE_TOO_LARGE",
                    "remote approval notification response exceeds the configured byte limit.",
                    max_bytes=self.max_response_bytes,
                )
            )
        if not 200 <= status < 300:
            return Result.err(
                _error(
                    "APPROVAL_NOTIFICATION_HTTP_ERROR",
                    "remote approval notification endpoint returned an error.",
                    status=status,
                )
            )
        try:
            decoded = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            return Result.err(
                _error(
                    "APPROVAL_NOTIFICATION_RESPONSE_INVALID",
                    "remote approval notification response is not valid JSON.",
                )
            )
        if not isinstance(decoded, dict) or decoded.get("accepted") is not True:
            return Result.err(
                _error(
                    "APPROVAL_NOTIFICATION_RESPONSE_INVALID",
                    "remote approval notification response did not acknowledge acceptance.",
                )
            )
        return Result.ok(None)


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

    def record_execution(
        self, approval_id: str, execution_result: Mapping[str, Any]
    ) -> Result[ApprovalRequest, Error]: ...

    def list_pending(
        self, limit: int = 100
    ) -> Result[List[ApprovalRequest], Error]: ...


def _copy_request(request: ApprovalRequest) -> ApprovalRequest:
    return ApprovalRequest.from_dict(request.to_dict())


class InMemoryApprovalStore:
    """Thread-safe approval store for local runs and contract tests."""

    def __init__(self, *, notifier: Optional[ApprovalNotifier] = None) -> None:
        self._requests: Dict[str, ApprovalRequest] = {}
        self._lock = threading.RLock()
        self._notifier = notifier
        if notifier is not None and not callable(getattr(notifier, "notify", None)):
            raise TypeError("approval notifier must implement notify")

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
            notified = _notify_host(self._notifier, candidate, "created")
            if notified.is_err():
                return Result.err(notified.unwrap_err())
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

    def record_execution(
        self, approval_id: str, execution_result: Mapping[str, Any]
    ) -> Result[ApprovalRequest, Error]:
        identifier_error = _valid_identifier(approval_id, "approval_id")
        if identifier_error:
            return Result.err(identifier_error)
        normalized = _copy_execution_result(execution_result)
        if normalized.is_err() or normalized.unwrap() is None:
            return Result.err(
                normalized.unwrap_err()
                if normalized.is_err()
                else _error(
                    "APPROVAL_EXECUTION_INVALID",
                    "Approval execution outcome is required.",
                )
            )
        with self._lock:
            request = self._requests.get(approval_id)
            if request is None:
                return Result.err(
                    _error("APPROVAL_NOT_FOUND", "Approval request was not found.")
                )
            if request.status != "consumed":
                return Result.err(
                    _error(
                        "APPROVAL_EXECUTION_CONFLICT",
                        "Only a consumed approval can record an execution outcome.",
                        status=request.status,
                    )
                )
            if request.execution_result is not None:
                if request.execution_result != normalized.unwrap():
                    return Result.err(
                        _error(
                            "APPROVAL_EXECUTION_CONFLICT",
                            "Approval execution outcome is already recorded.",
                        )
                    )
                return Result.ok(_copy_request(request))
            recorded = replace(
                request,
                execution_result=normalized.unwrap(),
                updated_at=time.time(),
            )
            self._requests[approval_id] = recorded
            return Result.ok(_copy_request(recorded))

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
            notified = _notify_host(
                self._notifier,
                decided,
                "approved" if approved else "denied",
            )
            if notified.is_err():
                return Result.err(notified.unwrap_err())
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
        notifier: Optional[ApprovalNotifier] = None,
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
        self._record_leases = DurableRecordLease(
            self.directory,
            namespace="approval",
            holder_label="approval",
            lease_manager=lease_manager,
            lease_ttl_seconds=lease_ttl_seconds,
        )
        self._notifier = notifier
        if notifier is not None and not callable(getattr(notifier, "notify", None)):
            raise TypeError("approval notifier must implement notify")

    def _with_record_lease(
        self,
        approval_id: str,
        operation: str,
        callback: Callable[[], Result[Any, Error]],
    ) -> Result[Any, Error]:
        return self._record_leases.run(
            approval_id,
            operation,
            callback,
            acquire_error_type="APPROVAL_LEASE_ERROR",
            acquire_error_message="Approval record lease is unavailable.",
            release_error_type="APPROVAL_LEASE_RELEASE_ERROR",
            release_error_message="Approval record lease could not be released safely.",
        )

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
                stored = self._write_unlocked(candidate)
                notified = _notify_host(self._notifier, stored, "created")
                if notified.is_err():
                    return Result.err(notified.unwrap_err())
                return Result.ok(stored)
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
                stored = self._write_unlocked(decided)
                notified = _notify_host(
                    self._notifier,
                    stored,
                    "approved" if approved else "denied",
                )
                if notified.is_err():
                    return Result.err(notified.unwrap_err())
                return Result.ok(stored)
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

    def record_execution(
        self, approval_id: str, execution_result: Mapping[str, Any]
    ) -> Result[ApprovalRequest, Error]:
        return self._with_record_lease(
            approval_id,
            "record_execution",
            lambda: self._record_execution_without_lease(approval_id, execution_result),
        )

    def _record_execution_without_lease(
        self, approval_id: str, execution_result: Mapping[str, Any]
    ) -> Result[ApprovalRequest, Error]:
        normalized = _copy_execution_result(execution_result)
        if normalized.is_err() or normalized.unwrap() is None:
            return Result.err(
                normalized.unwrap_err()
                if normalized.is_err()
                else _error(
                    "APPROVAL_EXECUTION_INVALID",
                    "Approval execution outcome is required.",
                )
            )
        try:
            with self._lock:
                request = self._read_unlocked(approval_id)
                if request is None:
                    return Result.err(
                        _error("APPROVAL_NOT_FOUND", "Approval request was not found.")
                    )
                if request.status != "consumed":
                    return Result.err(
                        _error(
                            "APPROVAL_EXECUTION_CONFLICT",
                            "Only a consumed approval can record an execution outcome.",
                            status=request.status,
                        )
                    )
                if request.execution_result is not None:
                    if request.execution_result != normalized.unwrap():
                        return Result.err(
                            _error(
                                "APPROVAL_EXECUTION_CONFLICT",
                                "Approval execution outcome is already recorded.",
                            )
                        )
                    return Result.ok(_copy_request(request))
                return Result.ok(
                    self._write_unlocked(
                        replace(
                            request,
                            execution_result=normalized.unwrap(),
                            updated_at=time.time(),
                        )
                    )
                )
        except (OSError, TypeError, ValueError, json.JSONDecodeError) as exc:
            return Result.err(
                _error(
                    "APPROVAL_SAVE_ERROR",
                    "Failed to record approval execution outcome.",
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
