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
"""Bounded event streaming and redaction primitives for MAPLE."""

from __future__ import annotations

import hashlib
import ipaddress
import json
import logging
import math
import os
import tempfile
import threading
import time
from collections import OrderedDict, deque
from dataclasses import dataclass, replace
from pathlib import Path
from typing import (
    Any,
    Callable,
    Deque,
    Dict,
    List,
    Mapping,
    Optional,
    Protocol,
    Sequence,
    Tuple,
    Union,
)
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit, urlunsplit
from urllib.request import Request

from ..core.result import Result
from .durable_leases import DurableRecordLease
from .http_transport import open_http_request

Error = Dict[str, Any]
EventCallback = Callable[["AgentEvent"], None]
_MAX_LATENCY_SAMPLES = 4_096
_DEFAULT_EXPORT_TIMEOUT_SECONDS = 5.0
_DEFAULT_EXPORT_MAX_EVENT_BYTES = 1_048_576
_DEFAULT_EXPORT_MAX_RESPONSE_BYTES = 64 * 1024
_MAX_EXPORT_PATH_BYTES = 4_096
DEFAULT_MAX_JOURNAL_BYTES = 16 * 1024 * 1024
DEFAULT_MAX_FORWARD_BATCH_ITEMS = 100
DEFAULT_MAX_CURSOR_BYTES = 4 * 1024
DEFAULT_FORWARD_INTERVAL_SECONDS = 1.0
DEFAULT_MAX_FORWARD_BATCHES_PER_TICK = 1
DEFAULT_MAX_EVENT_DEDUP_ENTRIES = 10_000
DEFAULT_EVENT_DEDUP_TTL_SECONDS = 3_600.0
DEFAULT_MAX_EVENT_DEDUP_BYTES = 16 * 1024 * 1024
DEFAULT_MAX_EVENT_SEARCH_LIMIT = 1_000
_EVENT_JOURNAL_VERSION = 1
_EVENT_CURSOR_VERSION = 1
_EVENT_DEDUPLICATION_VERSION = 1
_MAX_EVENT_PAYLOAD_ITEMS = 10_000
_MAX_EVENT_PAYLOAD_DEPTH = 32
_MAX_EVENT_SOURCE_ID_LENGTH = 256
_MAX_EVENT_DEDUP_BYTES = 256 * 1024 * 1024

logger = logging.getLogger(__name__)


def _percentile(values: List[int], percentile: int) -> int:
    """Return a bounded nearest-rank percentile for integer samples."""
    if not values:
        return 0
    ordered = sorted(values)
    rank = (percentile * len(ordered) + 99) // 100
    return ordered[min(len(ordered) - 1, max(0, rank - 1))]


class CancellationSignal(Protocol):
    """Minimal cooperative cancellation contract for event waiters."""

    def is_cancelled(self) -> bool:
        """Return whether cancellation has been requested."""


class EventExporter(Protocol):
    """Host-owned sink for already-redacted agent events."""

    def export(self, event: "AgentEvent") -> None:
        """Receive one bounded event without changing the run outcome."""


def _validate_export_token(auth_token: Optional[str]) -> None:
    if auth_token is None:
        return
    if not isinstance(auth_token, str) or not auth_token.strip():
        raise ValueError("auth_token must be a non-empty string when provided")
    if any(ord(character) < 0x20 or ord(character) == 0x7F for character in auth_token):
        raise ValueError("auth_token must not contain control characters")


class HttpEventExporter:
    """Synchronous, bounded HTTP delivery for already-redacted events.

    Delivery is best-effort: failures are raised to ``EventStream``, which
    records the exporter failure and preserves the published event. This class
    never retries or stores events for later delivery.
    """

    def __init__(
        self,
        endpoint: str,
        *,
        auth_token: Optional[str] = None,
        timeout_seconds: float = _DEFAULT_EXPORT_TIMEOUT_SECONDS,
        max_event_bytes: int = _DEFAULT_EXPORT_MAX_EVENT_BYTES,
        max_response_bytes: int = _DEFAULT_EXPORT_MAX_RESPONSE_BYTES,
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
            raise ValueError("endpoint must not include user information")
        if parsed.query or parsed.fragment:
            raise ValueError("endpoint must not include a query or fragment")
        _validate_export_token(auth_token)
        is_loopback = hostname.lower() == "localhost"
        if not is_loopback:
            try:
                is_loopback = ipaddress.ip_address(hostname).is_loopback
            except ValueError:
                is_loopback = False
        if parsed.scheme != "https" and not is_loopback:
            raise ValueError("non-loopback event export requires https")
        normalized_endpoint = urlunsplit(
            (parsed.scheme, parsed.netloc, parsed.path, "", "")
        )
        if len(normalized_endpoint.encode("utf-8")) > _MAX_EXPORT_PATH_BYTES:
            raise ValueError("endpoint URL is too large")
        if not isinstance(timeout_seconds, (int, float)) or isinstance(
            timeout_seconds, bool
        ):
            raise ValueError("timeout_seconds must be a positive number")
        try:
            normalized_timeout = float(timeout_seconds)
        except (OverflowError, ValueError) as exc:
            raise ValueError(
                "timeout_seconds must be a finite positive number"
            ) from exc
        if not math.isfinite(normalized_timeout) or normalized_timeout <= 0:
            raise ValueError("timeout_seconds must be a finite positive number")
        for value, name in (
            (max_event_bytes, "max_event_bytes"),
            (max_response_bytes, "max_response_bytes"),
        ):
            if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
                raise ValueError(f"{name} must be a positive integer")
        self.endpoint = normalized_endpoint
        self.auth_token = auth_token
        self.timeout_seconds = normalized_timeout
        self.max_event_bytes = max_event_bytes
        self.max_response_bytes = max_response_bytes

    def export(self, event: "AgentEvent") -> None:
        """POST one bounded event and raise on delivery failure."""
        if not isinstance(event, AgentEvent):
            raise TypeError("event must be an AgentEvent")
        try:
            encoded = json.dumps(
                event.as_dict(),
                ensure_ascii=False,
                allow_nan=False,
                separators=(",", ":"),
            ).encode("utf-8")
        except (TypeError, ValueError, OverflowError) as exc:
            raise ValueError("event must be JSON serializable") from exc
        if len(encoded) > self.max_event_bytes:
            raise ValueError("event exceeds the configured byte limit")
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
        }
        if self.auth_token is not None:
            headers["Authorization"] = f"Bearer {self.auth_token}"
        request = Request(
            self.endpoint,
            data=encoded,
            headers=headers,
            method="POST",
        )
        try:
            with open_http_request(request, timeout=self.timeout_seconds) as response:
                status = int(response.status)
                body = response.read(self.max_response_bytes + 1)
                if len(body) > self.max_response_bytes:
                    raise RuntimeError("event export response exceeds the byte limit")
                if not 200 <= status < 300:
                    raise RuntimeError("event export endpoint returned an error")
        except HTTPError as exc:
            exc.close()
            raise RuntimeError("event export endpoint returned an error") from None
        except (URLError, TimeoutError, OSError) as exc:
            raise RuntimeError("event export endpoint could not be reached") from exc


@dataclass(frozen=True)
class EventCursor:
    """Serializable position used to consume a bounded event stream."""

    sequence: int = 0

    def __post_init__(self) -> None:
        if (
            not isinstance(self.sequence, int)
            or isinstance(self.sequence, bool)
            or self.sequence < 0
        ):
            raise ValueError("sequence must be a non-negative integer")

    def to_dict(self) -> Dict[str, int]:
        """Return the JSON-safe cursor representation."""
        return {"sequence": self.sequence}

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> Result["EventCursor", Error]:
        """Parse a persisted cursor without accepting ambiguous state."""
        if not isinstance(value, Mapping):
            return Result.err(
                _error("EVENT_CURSOR_INVALID", "cursor must be an object.")
            )
        sequence = value.get("sequence")
        if not isinstance(sequence, int) or isinstance(sequence, bool) or sequence < 0:
            return Result.err(
                _error(
                    "EVENT_CURSOR_INVALID",
                    "cursor sequence must be a non-negative integer.",
                )
            )
        return Result.ok(cls(sequence=sequence))


def _error(error_type: str, message: str, **details: Any) -> Error:
    error: Error = {"errorType": error_type, "message": message}
    if details:
        error["details"] = details
    return error


def validate_event_source_id(value: Any) -> Optional[Error]:
    """Validate a bounded source identity used by remote event deduplication."""
    if (
        not isinstance(value, str)
        or not value
        or len(value) > _MAX_EVENT_SOURCE_ID_LENGTH
        or any(ord(char) < 32 or ord(char) == 127 for char in value)
    ):
        return _error(
            "EVENT_SOURCE_ID_INVALID",
            "source_id must be bounded and contain no control characters.",
            max_length=_MAX_EVENT_SOURCE_ID_LENGTH,
        )
    return None


def _json_size(value: Any) -> Result[int, Error]:
    try:
        size = len(
            json.dumps(
                value,
                ensure_ascii=False,
                separators=(",", ":"),
                allow_nan=False,
            ).encode("utf-8")
        )
    except (TypeError, ValueError, OverflowError):
        return Result.err(
            _error("EVENT_NON_JSON_PAYLOAD", "event payload must be JSON serializable.")
        )
    return Result.ok(size)


@dataclass(frozen=True)
class RedactionPolicy:
    """Recursive payload redaction and shape limits."""

    sensitive_keys: Tuple[str, ...] = (
        "api_key",
        "authorization",
        "credential",
        "password",
        "refresh_token",
        "secret",
        "token",
    )
    replacement: str = "[REDACTED]"
    max_depth: int = 12
    max_items: int = 10_000
    max_string_length: int = 65_536

    def validate(self) -> Optional[Error]:
        if not self.sensitive_keys or not all(
            isinstance(key, str) and key for key in self.sensitive_keys
        ):
            return _error(
                "EVENT_CONFIG_INVALID", "sensitive_keys must contain strings."
            )
        for name, value in (
            ("max_depth", self.max_depth),
            ("max_items", self.max_items),
            ("max_string_length", self.max_string_length),
        ):
            if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
                return _error("EVENT_CONFIG_INVALID", f"{name} must be positive.")
        if not isinstance(self.replacement, str) or not self.replacement:
            return _error(
                "EVENT_CONFIG_INVALID", "replacement must be a non-empty string."
            )
        return None

    def redact(self, value: Any) -> Result[Any, Error]:
        """Return a bounded redacted copy of a JSON-compatible value."""
        config_error = self.validate()
        if config_error is not None:
            return Result.err(config_error)

        def visit(current: Any, depth: int) -> Result[Any, Error]:
            if depth > self.max_depth:
                return Result.err(
                    _error(
                        "EVENT_PAYLOAD_TOO_DEEP", "event payload is too deeply nested."
                    )
                )
            if isinstance(current, str):
                if len(current) > self.max_string_length:
                    return Result.err(
                        _error(
                            "EVENT_PAYLOAD_TOO_LARGE",
                            "event string exceeds the length limit.",
                        )
                    )
                return Result.ok(current)
            if current is None or isinstance(current, (bool, int, float)):
                return Result.ok(current)
            if isinstance(current, list):
                if len(current) > self.max_items:
                    return Result.err(
                        _error(
                            "EVENT_PAYLOAD_TOO_LARGE",
                            "event array exceeds the item limit.",
                        )
                    )
                output_list: List[Any] = []
                for item in current:
                    item_result = visit(item, depth + 1)
                    if item_result.is_err():
                        return item_result
                    output_list.append(item_result.unwrap())
                return Result.ok(output_list)
            if isinstance(current, Mapping):
                if len(current) > self.max_items:
                    return Result.err(
                        _error(
                            "EVENT_PAYLOAD_TOO_LARGE",
                            "event object exceeds the item limit.",
                        )
                    )
                output_mapping: Dict[str, Any] = {}
                sensitive = {key.casefold() for key in self.sensitive_keys}
                for key, item in current.items():
                    if not isinstance(key, str):
                        return Result.err(
                            _error(
                                "EVENT_NON_JSON_PAYLOAD",
                                "event object keys must be strings.",
                            )
                        )
                    if key.casefold() in sensitive:
                        output_mapping[key] = self.replacement
                        continue
                    item_result = visit(item, depth + 1)
                    if item_result.is_err():
                        return item_result
                    output_mapping[key] = item_result.unwrap()
                return Result.ok(output_mapping)
            return Result.err(
                _error(
                    "EVENT_NON_JSON_PAYLOAD",
                    "event payload contains an unsupported value.",
                )
            )

        return visit(value, 0)


@dataclass(frozen=True)
class AgentEvent:
    """A sequenced, redacted, source-correlated agent event."""

    sequence: int
    event_type: str
    timestamp: float
    payload: Any
    run_id: Optional[str] = None

    def as_dict(self) -> Dict[str, Any]:
        """Return a JSON-compatible event mapping."""
        return {
            "sequence": self.sequence,
            "event_type": self.event_type,
            "timestamp": self.timestamp,
            "payload": self.payload,
            "run_id": self.run_id,
        }


@dataclass(frozen=True)
class EventBatch:
    """A bounded read result with a cursor safe to persist and resume."""

    events: Tuple[AgentEvent, ...]
    next_cursor: EventCursor
    oldest_sequence: Optional[int]
    latest_sequence: Optional[int]

    def to_dict(self) -> Dict[str, Any]:
        """Return the JSON-safe batch representation."""
        return {
            "events": [event.as_dict() for event in self.events],
            "next_cursor": self.next_cursor.to_dict(),
            "oldest_sequence": self.oldest_sequence,
            "latest_sequence": self.latest_sequence,
        }


@dataclass(frozen=True)
class EventDeliveryFailure:
    """A bounded remote rejection identified by its source batch index."""

    index: int
    error: Error

    def __post_init__(self) -> None:
        if (
            not isinstance(self.index, int)
            or isinstance(self.index, bool)
            or self.index < 0
        ):
            raise ValueError("index must be a non-negative integer")
        if not isinstance(self.error, Mapping):
            raise ValueError("error must be a mapping")

    def to_dict(self) -> Dict[str, Any]:
        """Return a JSON-safe failure representation."""
        return {"index": self.index, "error": dict(self.error)}


@dataclass(frozen=True)
class EventDelivery:
    """The bounded acknowledgement returned by an event batch destination."""

    published: Tuple[int, ...]
    failed: Tuple[EventDeliveryFailure, ...]

    def to_dict(self) -> Dict[str, Any]:
        """Return the delivery acknowledgement without event payloads."""
        return {
            "published": list(self.published),
            "failed": [failure.to_dict() for failure in self.failed],
        }


@dataclass(frozen=True)
class EventForwardReport:
    """One bounded forwarding attempt and its durable cursor outcome."""

    cursor: EventCursor
    next_cursor: EventCursor
    published: Tuple[int, ...]
    failed: Tuple[EventDeliveryFailure, ...]

    @property
    def attempted(self) -> int:
        """Return the number of source events included in the attempt."""
        return len(self.published) + len(self.failed)

    @property
    def cursor_advanced(self) -> bool:
        """Return whether the durable cursor moved during this attempt."""
        return self.next_cursor != self.cursor

    def to_dict(self) -> Dict[str, Any]:
        """Return bounded forwarding metrics and indexed outcomes."""
        return {
            "cursor": self.cursor.to_dict(),
            "next_cursor": self.next_cursor.to_dict(),
            "attempted": self.attempted,
            "published": list(self.published),
            "failed": [failure.to_dict() for failure in self.failed],
            "cursor_advanced": self.cursor_advanced,
        }


@dataclass(frozen=True)
class EventForwarderSchedulerStats:
    """Bounded counters for an opt-in event-forwarder scheduler."""

    ticks: int = 0
    batches: int = 0
    events_attempted: int = 0
    events_published: int = 0
    events_failed: int = 0
    forward_errors: int = 0
    running: bool = False
    last_error: Optional[Error] = None

    def to_dict(self) -> Dict[str, Any]:
        """Return a JSON-safe metrics snapshot without remote error text."""
        return {
            "ticks": self.ticks,
            "batches": self.batches,
            "events_attempted": self.events_attempted,
            "events_published": self.events_published,
            "events_failed": self.events_failed,
            "forward_errors": self.forward_errors,
            "running": self.running,
            "last_error": dict(self.last_error) if self.last_error else None,
        }


class EventBatchSender(Protocol):
    """Host-owned destination for one bounded group of redacted events."""

    def send(self, events: Sequence[AgentEvent]) -> Result[EventDelivery, Error]:
        """Deliver events and return a complete indexed acknowledgement."""


class EventDeduplicationStore(Protocol):
    """Host-owned bounded claim/complete contract for forwarded events."""

    def claim(
        self,
        source_id: str,
        source_sequence: int,
        event: AgentEvent,
    ) -> Result[Optional[AgentEvent], Error]:
        """Claim an event or return its already completed destination event."""

    def complete(
        self, source_id: str, source_sequence: int, event: AgentEvent
    ) -> Result[AgentEvent, Error]:
        """Record the destination event after successful stream publication."""

    def abort(self, source_id: str, source_sequence: int) -> Result[None, Error]:
        """Release an incomplete claim after a failed publication."""


class EventCursorStore(Protocol):
    """Durable position contract for a forwarding consumer."""

    def load(self) -> Result[EventCursor, Error]:
        """Load the last contiguous source sequence acknowledged."""

    def save(self, cursor: EventCursor) -> Result[EventCursor, Error]:
        """Advance the cursor without allowing regression."""


class InMemoryEventCursorStore:
    """Thread-safe cursor store for one-process forwarding consumers."""

    def __init__(self, cursor: Optional[EventCursor] = None) -> None:
        if cursor is not None and not isinstance(cursor, EventCursor):
            raise TypeError("cursor must be an EventCursor when provided")
        self._cursor = cursor or EventCursor()
        self._lock = threading.RLock()

    def load(self) -> Result[EventCursor, Error]:
        """Return the current immutable cursor."""
        with self._lock:
            return Result.ok(self._cursor)

    def save(self, cursor: EventCursor) -> Result[EventCursor, Error]:
        """Persist a non-regressing cursor in memory."""
        if not isinstance(cursor, EventCursor):
            return Result.err(_error("EVENT_CURSOR_INVALID", "cursor is invalid."))
        with self._lock:
            if cursor.sequence < self._cursor.sequence:
                return Result.err(
                    _error(
                        "EVENT_CURSOR_CONFLICT",
                        "cursor cannot move backwards.",
                        current_sequence=self._cursor.sequence,
                        requested_sequence=cursor.sequence,
                    )
                )
            self._cursor = cursor
            return Result.ok(cursor)


class FileEventCursorStore:
    """Atomic, bounded, cross-process cursor persistence for one forwarder."""

    _FILENAME = "cursor.json"
    _TEMP_PREFIX = ".maple-event-cursor-"

    def __init__(
        self,
        directory: Union[str, Path],
        *,
        max_bytes: int = DEFAULT_MAX_CURSOR_BYTES,
        lease_ttl_seconds: float = 30.0,
    ) -> None:
        if (
            not isinstance(max_bytes, int)
            or isinstance(max_bytes, bool)
            or max_bytes <= 0
        ):
            raise ValueError("max_bytes must be a positive integer")
        self.max_bytes = max_bytes
        self.directory = Path(directory)
        try:
            self.directory.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            raise ValueError("event cursor directory is unavailable") from exc
        if not self.directory.is_dir():
            raise ValueError("event cursor path must be a directory")
        self.path = self.directory / self._FILENAME
        self._lock = threading.RLock()
        try:
            self._lease = DurableRecordLease(
                self.directory,
                namespace="event-forwarder",
                holder_label="file-event-cursor",
                lease_ttl_seconds=lease_ttl_seconds,
            )
        except (OSError, TypeError, ValueError) as exc:
            raise ValueError("event cursor lease is unavailable") from exc

    def _read_unlocked(self) -> Result[EventCursor, Error]:
        if not self.path.exists():
            return Result.ok(EventCursor())
        try:
            if self.path.stat().st_size > self.max_bytes:
                return Result.err(
                    _error(
                        "EVENT_CURSOR_LOAD_ERROR",
                        "event cursor exceeds the byte limit.",
                    )
                )
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, TypeError, ValueError, json.JSONDecodeError):
            return Result.err(
                _error("EVENT_CURSOR_LOAD_ERROR", "event cursor could not be loaded.")
            )
        if (
            not isinstance(data, Mapping)
            or not isinstance(data.get("version"), int)
            or isinstance(data.get("version"), bool)
            or data.get("version") != _EVENT_CURSOR_VERSION
        ):
            return Result.err(
                _error("EVENT_CURSOR_LOAD_ERROR", "event cursor version is invalid.")
            )
        raw_cursor = data.get("cursor")
        if not isinstance(raw_cursor, Mapping):
            return Result.err(
                _error("EVENT_CURSOR_LOAD_ERROR", "event cursor record is invalid.")
            )
        parsed = EventCursor.from_dict(raw_cursor)
        if parsed.is_err():
            return Result.err(
                _error("EVENT_CURSOR_LOAD_ERROR", "event cursor record is invalid.")
            )
        return parsed

    def _encode(self, cursor: EventCursor) -> Result[str, Error]:
        try:
            encoded = json.dumps(
                {"version": _EVENT_CURSOR_VERSION, "cursor": cursor.to_dict()},
                ensure_ascii=False,
                allow_nan=False,
                separators=(",", ":"),
            )
        except (TypeError, ValueError, OverflowError):
            return Result.err(
                _error("EVENT_CURSOR_SAVE_ERROR", "event cursor is not serializable.")
            )
        if len(encoded.encode("utf-8")) > self.max_bytes:
            return Result.err(
                _error(
                    "EVENT_CURSOR_SIZE",
                    "event cursor exceeds the byte limit.",
                    max_bytes=self.max_bytes,
                )
            )
        return Result.ok(encoded)

    def _write_unlocked(self, cursor: EventCursor) -> Result[EventCursor, Error]:
        encoded = self._encode(cursor)
        if encoded.is_err():
            return Result.err(encoded.unwrap_err())
        temporary_path: Optional[Path] = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                dir=str(self.directory),
                prefix=self._TEMP_PREFIX,
                suffix=".tmp",
                delete=False,
            ) as handle:
                temporary_path = Path(handle.name)
                handle.write(encoded.unwrap())
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(str(temporary_path), str(self.path))
            temporary_path = None
            return Result.ok(cursor)
        except (OSError, TypeError, ValueError) as exc:
            return Result.err(
                _error(
                    "EVENT_CURSOR_SAVE_ERROR",
                    "event cursor could not be saved.",
                    reason=type(exc).__name__,
                )
            )
        finally:
            if temporary_path is not None:
                try:
                    temporary_path.unlink()
                except OSError:
                    pass

    def _run(
        self,
        operation: str,
        callback: Callable[[], Result[Any, Error]],
    ) -> Result[Any, Error]:
        try:
            return self._lease.run(
                "cursor",
                operation,
                callback,
                acquire_error_type="EVENT_CURSOR_LEASE_ERROR",
                acquire_error_message="event cursor lease could not be acquired.",
                release_error_type="EVENT_CURSOR_LEASE_RELEASE_ERROR",
                release_error_message="event cursor lease could not be released.",
            )
        except Exception as exc:
            return Result.err(
                _error(
                    "EVENT_CURSOR_ERROR",
                    "event cursor operation failed.",
                    operation=operation,
                    reason=type(exc).__name__,
                )
            )

    def load(self) -> Result[EventCursor, Error]:
        """Load the cursor under a fencing lease."""
        with self._lock:
            result = self._run("load", self._read_unlocked)
        if result.is_err():
            return Result.err(result.unwrap_err())
        return Result.ok(result.unwrap())

    def save(self, cursor: EventCursor) -> Result[EventCursor, Error]:
        """Atomically save a cursor that does not regress."""
        if not isinstance(cursor, EventCursor):
            return Result.err(_error("EVENT_CURSOR_INVALID", "cursor is invalid."))

        def operation() -> Result[EventCursor, Error]:
            current = self._read_unlocked()
            if current.is_err():
                return Result.err(current.unwrap_err())
            if cursor.sequence < current.unwrap().sequence:
                return Result.err(
                    _error(
                        "EVENT_CURSOR_CONFLICT",
                        "cursor cannot move backwards.",
                        current_sequence=current.unwrap().sequence,
                        requested_sequence=cursor.sequence,
                    )
                )
            return self._write_unlocked(cursor)

        with self._lock:
            result = self._run("save", operation)
        if result.is_err():
            return Result.err(result.unwrap_err())
        return Result.ok(result.unwrap())


def _validate_event_delivery(
    delivery: Any, expected_count: int
) -> Result[EventDelivery, Error]:
    """Require a complete, duplicate-free acknowledgement partition."""
    if not isinstance(delivery, EventDelivery):
        return Result.err(
            _error("EVENT_DELIVERY_INVALID", "event delivery is not typed.")
        )
    published = list(delivery.published)
    failed = list(delivery.failed)
    all_indices = published + [failure.index for failure in failed]
    if (
        any(
            not isinstance(index, int)
            or isinstance(index, bool)
            or index < 0
            or index >= expected_count
            for index in all_indices
        )
        or len(set(all_indices)) != expected_count
        or len(all_indices) != expected_count
    ):
        return Result.err(
            _error(
                "EVENT_DELIVERY_INVALID",
                "event delivery must acknowledge every source item exactly once.",
                expected_items=expected_count,
            )
        )
    return Result.ok(delivery)


class EventForwarder:
    """Forward one bounded source window with a durable at-least-once cursor.

    The source stream and cursor store are host-owned. Calls on one instance
    are serialized; separate processes may resend an already-accepted batch
    if a cursor save or response is lost. The class never claims exactly-once
    delivery and never retries implicitly.
    """

    def __init__(
        self,
        stream: EventStream,
        sender: EventBatchSender,
        cursor_store: EventCursorStore,
        *,
        max_batch_size: int = DEFAULT_MAX_FORWARD_BATCH_ITEMS,
    ) -> None:
        if not callable(getattr(stream, "read", None)):
            raise TypeError("stream must implement read")
        if not callable(getattr(sender, "send", None)):
            raise TypeError("sender must implement send")
        if not callable(getattr(cursor_store, "load", None)) or not callable(
            getattr(cursor_store, "save", None)
        ):
            raise TypeError("cursor_store must implement load and save")
        if (
            not isinstance(max_batch_size, int)
            or isinstance(max_batch_size, bool)
            or not 1 <= max_batch_size <= DEFAULT_MAX_FORWARD_BATCH_ITEMS
        ):
            raise ValueError(
                "max_batch_size must be between 1 and "
                f"{DEFAULT_MAX_FORWARD_BATCH_ITEMS}"
            )
        self.stream = stream
        self.sender = sender
        self.cursor_store = cursor_store
        self.max_batch_size = max_batch_size
        self._lock = threading.Lock()

    def forward(self) -> Result[EventForwardReport, Error]:
        """Forward one source batch and persist only its acknowledged prefix."""
        with self._lock:
            try:
                cursor_result = self.cursor_store.load()
            except Exception as exc:
                return Result.err(
                    _error(
                        "EVENT_FORWARD_CURSOR_ERROR",
                        "event forward cursor could not be loaded.",
                        reason=type(exc).__name__,
                    )
                )
            if cursor_result.is_err():
                return Result.err(cursor_result.unwrap_err())
            cursor = cursor_result.unwrap()
            if not isinstance(cursor, EventCursor):
                return Result.err(
                    _error(
                        "EVENT_CURSOR_INVALID",
                        "cursor store returned an invalid cursor.",
                    )
                )
            try:
                batch_result = self.stream.read(cursor, limit=self.max_batch_size)
            except Exception as exc:
                return Result.err(
                    _error(
                        "EVENT_FORWARD_SOURCE_ERROR",
                        "event source could not be read.",
                        reason=type(exc).__name__,
                    )
                )
            if batch_result.is_err():
                return Result.err(batch_result.unwrap_err())
            batch = batch_result.unwrap()
            if not isinstance(batch, EventBatch):
                return Result.err(
                    _error(
                        "EVENT_FORWARD_SOURCE_ERROR",
                        "event source returned an invalid batch.",
                    )
                )
            events = batch.events
            if not events:
                return Result.ok(
                    EventForwardReport(
                        cursor=cursor,
                        next_cursor=cursor,
                        published=(),
                        failed=(),
                    )
                )
            try:
                delivery_result = self.sender.send(events)
            except Exception as exc:
                return Result.err(
                    _error(
                        "EVENT_FORWARD_TRANSPORT_ERROR",
                        "event batch delivery failed.",
                        reason=type(exc).__name__,
                    )
                )
            if delivery_result.is_err():
                return Result.err(delivery_result.unwrap_err())
            validated = _validate_event_delivery(delivery_result.unwrap(), len(events))
            if validated.is_err():
                return Result.err(validated.unwrap_err())
            delivery = validated.unwrap()
            published_indices = set(delivery.published)
            contiguous_count = 0
            while (
                contiguous_count < len(events) and contiguous_count in published_indices
            ):
                contiguous_count += 1
            next_cursor = cursor
            if contiguous_count:
                next_cursor = EventCursor(
                    sequence=events[contiguous_count - 1].sequence
                )
                try:
                    saved = self.cursor_store.save(next_cursor)
                except Exception as exc:
                    return Result.err(
                        _error(
                            "EVENT_FORWARD_CURSOR_ERROR",
                            "event forward cursor could not be saved.",
                            reason=type(exc).__name__,
                        )
                    )
                if saved.is_err():
                    return Result.err(saved.unwrap_err())
                if saved.unwrap() != next_cursor:
                    return Result.err(
                        _error(
                            "EVENT_CURSOR_CONFLICT",
                            "cursor store returned a different cursor.",
                        )
                    )
            return Result.ok(
                EventForwardReport(
                    cursor=cursor,
                    next_cursor=next_cursor,
                    published=delivery.published,
                    failed=delivery.failed,
                )
            )


class EventForwarderScheduler:
    """Run an :class:`EventForwarder` on an explicit bounded schedule.

    The scheduler owns one non-daemon worker after ``start()`` and never
    creates a queue. At most one forward operation is in flight, and each tick
    drains at most ``max_batches_per_tick`` source windows. ``stop()`` is
    cooperative and reports a timeout if a host sender ignores its own
    deadline; the worker remains owned by this scheduler until it exits.
    """

    def __init__(
        self,
        forwarder: EventForwarder,
        *,
        interval_seconds: float = DEFAULT_FORWARD_INTERVAL_SECONDS,
        max_batches_per_tick: int = DEFAULT_MAX_FORWARD_BATCHES_PER_TICK,
    ) -> None:
        if not callable(getattr(forwarder, "forward", None)):
            raise TypeError("forwarder must implement forward")
        try:
            interval_is_finite = math.isfinite(float(interval_seconds))
        except (OverflowError, TypeError, ValueError):
            interval_is_finite = False
        if (
            not isinstance(interval_seconds, (int, float))
            or isinstance(interval_seconds, bool)
            or not interval_is_finite
            or interval_seconds < 0.01
            or interval_seconds > 86_400.0
        ):
            raise ValueError("interval_seconds must be between 0.01 and 86400")
        if (
            not isinstance(max_batches_per_tick, int)
            or isinstance(max_batches_per_tick, bool)
            or not 1 <= max_batches_per_tick <= DEFAULT_MAX_FORWARD_BATCH_ITEMS
        ):
            raise ValueError(
                "max_batches_per_tick must be between 1 and "
                f"{DEFAULT_MAX_FORWARD_BATCH_ITEMS}"
            )
        self.forwarder = forwarder
        self.interval_seconds = float(interval_seconds)
        self.max_batches_per_tick = max_batches_per_tick
        self._state_lock = threading.RLock()
        self._stop_event = threading.Event()
        self._active_tick = False
        self._thread: Optional[threading.Thread] = None
        self._stats = EventForwarderSchedulerStats()

    def _is_running_unlocked(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    @staticmethod
    def _safe_error(error: Any) -> Error:
        cause = error.get("errorType") if isinstance(error, Mapping) else None
        if (
            not isinstance(cause, str)
            or not cause
            or len(cause) > 128
            or any(ord(char) < 32 or ord(char) == 127 for char in cause)
        ):
            cause = "FORWARD_ERROR"
        return _error(
            "EVENT_SCHEDULER_FORWARD_ERROR",
            "scheduled event forwarding failed.",
            cause=cause,
        )

    def _record_error(self, error: Any) -> Error:
        safe_error = self._safe_error(error)
        with self._state_lock:
            self._stats = replace(
                self._stats,
                forward_errors=self._stats.forward_errors + 1,
                last_error=safe_error,
            )
        details = safe_error.get("details")
        cause = (
            details.get("cause") if isinstance(details, Mapping) else "FORWARD_ERROR"
        )
        logger.warning("event forwarder scheduler tick failed: cause=%s", cause)
        return safe_error

    def _record_report(self, report: EventForwardReport) -> None:
        with self._state_lock:
            self._stats = replace(
                self._stats,
                batches=self._stats.batches + (1 if report.attempted else 0),
                events_attempted=self._stats.events_attempted + report.attempted,
                events_published=self._stats.events_published + len(report.published),
                events_failed=self._stats.events_failed + len(report.failed),
            )

    def _claim_tick(self) -> bool:
        with self._state_lock:
            if self._active_tick:
                return False
            self._active_tick = True
            self._stats = replace(self._stats, ticks=self._stats.ticks + 1)
            return True

    def _release_tick(self) -> None:
        with self._state_lock:
            self._active_tick = False

    def _run_tick(
        self,
    ) -> Result[Tuple[EventForwardReport, ...], Error]:
        if not self._claim_tick():
            return Result.err(
                _error(
                    "EVENT_SCHEDULER_BUSY",
                    "another event-forwarder tick is already in flight.",
                )
            )
        reports: List[EventForwardReport] = []
        try:
            for _ in range(self.max_batches_per_tick):
                try:
                    result = self.forwarder.forward()
                except Exception as exc:
                    return Result.err(
                        self._record_error(
                            _error(
                                "EVENT_FORWARD_TRANSPORT_ERROR",
                                "event forwarding raised an exception.",
                                reason=type(exc).__name__,
                            )
                        )
                    )
                if not isinstance(result, Result):
                    return Result.err(
                        self._record_error(
                            _error(
                                "EVENT_SCHEDULER_FORWARD_ERROR",
                                "event forwarder returned an invalid result.",
                            )
                        )
                    )
                if result.is_err():
                    return Result.err(self._record_error(result.unwrap_err()))
                report = result.unwrap()
                if not isinstance(report, EventForwardReport):
                    return Result.err(
                        self._record_error(
                            _error(
                                "EVENT_SCHEDULER_FORWARD_ERROR",
                                "event forwarder returned an invalid report.",
                            )
                        )
                    )
                self._record_report(report)
                reports.append(report)
                if report.attempted == 0:
                    break
            return Result.ok(tuple(reports))
        finally:
            self._release_tick()

    def _run(self) -> None:
        while not self._stop_event.is_set():
            started = time.monotonic()
            self._run_tick()
            elapsed = time.monotonic() - started
            wait_seconds = max(0.0, self.interval_seconds - elapsed)
            if self._stop_event.wait(wait_seconds):
                break

    def start(self) -> Result[None, Error]:
        """Start the owned worker; startup is never implicit."""
        with self._state_lock:
            if self._is_running_unlocked():
                return Result.err(
                    _error(
                        "EVENT_SCHEDULER_RUNNING",
                        "event-forwarder scheduler is already running.",
                    )
                )
            self._stop_event.clear()
            worker = threading.Thread(
                target=self._run,
                name="maple-event-forwarder",
                daemon=False,
            )
            self._thread = worker
        try:
            worker.start()
        except RuntimeError as exc:
            with self._state_lock:
                if self._thread is worker:
                    self._thread = None
            return Result.err(
                _error(
                    "EVENT_SCHEDULER_START_ERROR",
                    "event-forwarder scheduler could not start.",
                    reason=type(exc).__name__,
                )
            )
        return Result.ok(None)

    def run_once(self) -> Result[Tuple[EventForwardReport, ...], Error]:
        """Run one bounded tick synchronously when the scheduler is stopped."""
        with self._state_lock:
            if self._is_running_unlocked():
                return Result.err(
                    _error(
                        "EVENT_SCHEDULER_RUNNING",
                        "run_once is unavailable while the scheduler is running.",
                    )
                )
        return self._run_tick()

    def stop(self, *, timeout_seconds: float = 10.0) -> Result[None, Error]:
        """Request cooperative shutdown and wait for the owned worker."""
        try:
            timeout_is_finite = math.isfinite(float(timeout_seconds))
        except (OverflowError, TypeError, ValueError):
            timeout_is_finite = False
        if (
            not isinstance(timeout_seconds, (int, float))
            or isinstance(timeout_seconds, bool)
            or not timeout_is_finite
            or timeout_seconds < 0.0
            or timeout_seconds > 86_400.0
        ):
            return Result.err(
                _error(
                    "EVENT_SCHEDULER_TIMEOUT_INVALID",
                    "timeout_seconds must be between 0 and 86400.",
                )
            )
        with self._state_lock:
            worker = self._thread
            if worker is None:
                return Result.ok(None)
            if worker is threading.current_thread():
                return Result.err(
                    _error(
                        "EVENT_SCHEDULER_STOP_INVALID",
                        "scheduler cannot stop itself from its worker.",
                    )
                )
            self._stop_event.set()
        worker.join(timeout=float(timeout_seconds))
        if worker.is_alive():
            return Result.err(
                _error(
                    "EVENT_SCHEDULER_STOP_TIMEOUT",
                    "event-forwarder scheduler did not stop before the deadline.",
                )
            )
        with self._state_lock:
            if self._thread is worker:
                self._thread = None
        return Result.ok(None)

    def metrics(self) -> EventForwarderSchedulerStats:
        """Return a thread-safe bounded metrics snapshot."""
        with self._state_lock:
            last_error = (
                dict(self._stats.last_error) if self._stats.last_error else None
            )
            return replace(
                self._stats,
                running=self._is_running_unlocked(),
                last_error=last_error,
            )


def _remote_delivery_error(value: Any, index: int) -> Result[Error, Error]:
    """Keep remote item errors bounded and free of remote message text."""
    if not isinstance(value, Mapping):
        return Result.err(
            _error(
                "EVENT_DELIVERY_INVALID",
                "remote delivery failure is not an object.",
                index=index,
            )
        )
    error_type = value.get("errorType")
    if (
        not isinstance(error_type, str)
        or not error_type
        or len(error_type) > 128
        or any(ord(char) < 32 or ord(char) == 127 for char in error_type)
    ):
        return Result.err(
            _error(
                "EVENT_DELIVERY_INVALID",
                "remote delivery failure has an invalid error type.",
                index=index,
            )
        )
    return Result.ok(
        _error(
            "EVENT_REMOTE_ITEM_FAILED",
            "remote event item was rejected.",
            index=index,
            remote_error_type=error_type,
        )
    )


def _parse_event_delivery(
    value: Any, expected_count: int
) -> Result[EventDelivery, Error]:
    """Parse and validate the public batch acknowledgement shape."""
    if not isinstance(value, Mapping):
        return Result.err(
            _error(
                "EVENT_DELIVERY_INVALID", "event delivery response must be an object."
            )
        )
    raw_published = value.get("published")
    raw_failed = value.get("failed")
    if not isinstance(raw_published, list) or not isinstance(raw_failed, list):
        return Result.err(
            _error(
                "EVENT_DELIVERY_INVALID",
                "event delivery response must contain published and failed lists.",
            )
        )
    if len(raw_published) > expected_count or len(raw_failed) > expected_count:
        return Result.err(
            _error(
                "EVENT_DELIVERY_INVALID",
                "event delivery response exceeds the source batch size.",
                expected_items=expected_count,
            )
        )
    published: List[int] = []
    for item in raw_published:
        if not isinstance(item, Mapping):
            return Result.err(
                _error("EVENT_DELIVERY_INVALID", "published delivery item is invalid.")
            )
        index = item.get("index")
        if not isinstance(index, int) or isinstance(index, bool):
            return Result.err(
                _error("EVENT_DELIVERY_INVALID", "published delivery index is invalid.")
            )
        published.append(index)
    failed: List[EventDeliveryFailure] = []
    for item in raw_failed:
        if not isinstance(item, Mapping):
            return Result.err(
                _error("EVENT_DELIVERY_INVALID", "failed delivery item is invalid.")
            )
        index = item.get("index")
        if not isinstance(index, int) or isinstance(index, bool):
            return Result.err(
                _error("EVENT_DELIVERY_INVALID", "failed delivery index is invalid.")
            )
        failure_error = _remote_delivery_error(item.get("error"), index)
        if failure_error.is_err():
            return Result.err(failure_error.unwrap_err())
        failed.append(EventDeliveryFailure(index=index, error=failure_error.unwrap()))
    delivery = EventDelivery(published=tuple(published), failed=tuple(failed))
    return _validate_event_delivery(delivery, expected_count)


class HttpEventBatchSender(HttpEventExporter):
    """Dependency-free HTTP batch destination for :class:`EventForwarder`.

    Events are re-redacted before serialization. The sender performs one
    bounded request and never retries or stores a request locally.
    """

    def __init__(
        self,
        endpoint: str,
        *,
        auth_token: Optional[str] = None,
        source_id: Optional[str] = None,
        timeout_seconds: float = _DEFAULT_EXPORT_TIMEOUT_SECONDS,
        max_request_bytes: int = _DEFAULT_EXPORT_MAX_EVENT_BYTES,
        max_response_bytes: int = _DEFAULT_EXPORT_MAX_RESPONSE_BYTES,
        redaction: Optional[RedactionPolicy] = None,
    ) -> None:
        super().__init__(
            endpoint,
            auth_token=auth_token,
            timeout_seconds=timeout_seconds,
            max_event_bytes=max_request_bytes,
            max_response_bytes=max_response_bytes,
        )
        self.max_request_bytes = max_request_bytes
        self.redaction = redaction or RedactionPolicy()
        source_error = (
            validate_event_source_id(source_id) if source_id is not None else None
        )
        if source_error is not None:
            raise ValueError(source_error["message"])
        self.source_id = source_id
        config_error = self.redaction.validate()
        if config_error is not None:
            raise ValueError(config_error["message"])

    def send(self, events: Sequence[AgentEvent]) -> Result[EventDelivery, Error]:
        """Send one bounded event group and parse its complete acknowledgement."""
        if (
            not isinstance(events, (list, tuple))
            or not events
            or len(events) > DEFAULT_MAX_FORWARD_BATCH_ITEMS
        ):
            return Result.err(
                _error(
                    "EVENT_BATCH_INVALID",
                    "events must contain between 1 and 100 items.",
                    max_items=DEFAULT_MAX_FORWARD_BATCH_ITEMS,
                )
            )
        normalized: List[Dict[str, Any]] = []
        for index, event in enumerate(events):
            invalid = _validate_event_record(event)
            if invalid is not None:
                return Result.err(
                    _error(
                        "EVENT_FORWARD_INPUT_INVALID",
                        "source event is invalid.",
                        index=index,
                    )
                )
            redacted = self.redaction.redact(event.payload)
            if redacted.is_err():
                return Result.err(
                    _error(
                        "EVENT_FORWARD_INPUT_INVALID",
                        "source event payload failed redaction.",
                        index=index,
                    )
                )
            item: Dict[str, Any] = {
                "event_type": event.event_type,
                "payload": redacted.unwrap(),
            }
            if self.source_id is not None:
                item["sequence"] = event.sequence
            if event.run_id is not None:
                item["run_id"] = event.run_id
            normalized.append(item)
        try:
            encoded = json.dumps(
                {
                    "events": normalized,
                    **(
                        {"source_id": self.source_id}
                        if self.source_id is not None
                        else {}
                    ),
                },
                ensure_ascii=False,
                allow_nan=False,
                separators=(",", ":"),
            ).encode("utf-8")
        except (TypeError, ValueError, OverflowError) as exc:
            return Result.err(
                _error(
                    "EVENT_FORWARD_INPUT_INVALID",
                    "event batch is not JSON serializable.",
                    reason=type(exc).__name__,
                )
            )
        if len(encoded) > self.max_request_bytes:
            return Result.err(
                _error(
                    "EVENT_FORWARD_REQUEST_TOO_LARGE",
                    "event batch exceeds the request byte limit.",
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
            with open_http_request(request, timeout=self.timeout_seconds) as response:
                status = int(response.status)
                raw = response.read(self.max_response_bytes + 1)
        except HTTPError as exc:
            exc.close()
            return Result.err(
                _error(
                    "EVENT_FORWARD_HTTP_ERROR",
                    "remote event endpoint returned an error.",
                    status=int(exc.code),
                )
            )
        except (URLError, TimeoutError, OSError) as exc:
            return Result.err(
                _error(
                    "EVENT_FORWARD_TRANSPORT_ERROR",
                    "remote event endpoint could not be reached.",
                    reason=type(exc).__name__,
                )
            )
        if len(raw) > self.max_response_bytes:
            return Result.err(
                _error(
                    "EVENT_FORWARD_RESPONSE_TOO_LARGE",
                    "remote event response exceeds the byte limit.",
                    max_bytes=self.max_response_bytes,
                )
            )
        if not 200 <= status < 300:
            return Result.err(
                _error(
                    "EVENT_FORWARD_HTTP_ERROR",
                    "remote event endpoint returned an error.",
                    status=status,
                )
            )
        try:
            decoded = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            return Result.err(
                _error(
                    "EVENT_FORWARD_RESPONSE_INVALID",
                    "remote event response is not valid JSON.",
                )
            )
        return _parse_event_delivery(decoded, len(events))


class EventJournal(Protocol):
    """Host-owned persistence contract for a bounded event window."""

    def load(self) -> Result[List[AgentEvent], Error]:
        """Load the retained events in sequence order."""

    def append(self, event: AgentEvent) -> Result[AgentEvent, Error]:
        """Durably append one event before it is published."""


def _validate_event_value(value: Any, *, depth: int = 0) -> Optional[Error]:
    if depth > _MAX_EVENT_PAYLOAD_DEPTH:
        return _error(
            "EVENT_JOURNAL_RECORD_INVALID",
            "event payload is nested too deeply.",
        )
    if value is None or isinstance(value, (bool, int, str)):
        return None
    if isinstance(value, float):
        if math.isfinite(value):
            return None
        return _error(
            "EVENT_JOURNAL_RECORD_INVALID",
            "event payload contains a non-finite number.",
        )
    if isinstance(value, list):
        if len(value) > _MAX_EVENT_PAYLOAD_ITEMS:
            return _error(
                "EVENT_JOURNAL_RECORD_INVALID",
                "event payload array exceeds the item limit.",
            )
        for item in value:
            invalid = _validate_event_value(item, depth=depth + 1)
            if invalid is not None:
                return invalid
        return None
    if isinstance(value, dict):
        if len(value) > _MAX_EVENT_PAYLOAD_ITEMS:
            return _error(
                "EVENT_JOURNAL_RECORD_INVALID",
                "event payload object exceeds the item limit.",
            )
        for key, item in value.items():
            if not isinstance(key, str):
                return _error(
                    "EVENT_JOURNAL_RECORD_INVALID",
                    "event payload object keys must be strings.",
                )
            invalid = _validate_event_value(item, depth=depth + 1)
            if invalid is not None:
                return invalid
        return None
    return _error(
        "EVENT_JOURNAL_RECORD_INVALID",
        "event payload must be JSON-compatible.",
    )


def _validate_event_record(event: Any) -> Optional[Error]:
    if not isinstance(event, AgentEvent):
        return _error("EVENT_JOURNAL_RECORD_INVALID", "event must be an AgentEvent.")
    if (
        not isinstance(event.sequence, int)
        or isinstance(event.sequence, bool)
        or event.sequence <= 0
    ):
        return _error(
            "EVENT_JOURNAL_RECORD_INVALID",
            "event sequence must be a positive integer.",
        )
    if (
        not isinstance(event.event_type, str)
        or not event.event_type
        or len(event.event_type) > 128
        or any(ord(char) < 32 or ord(char) == 127 for char in event.event_type)
    ):
        return _error(
            "EVENT_JOURNAL_RECORD_INVALID",
            "event_type must be bounded and contain no control characters.",
        )
    timestamp_valid = isinstance(event.timestamp, (int, float)) and not isinstance(
        event.timestamp, bool
    )
    if timestamp_valid:
        try:
            timestamp_valid = math.isfinite(float(event.timestamp))
        except (OverflowError, ValueError):
            timestamp_valid = False
    if not timestamp_valid:
        return _error(
            "EVENT_JOURNAL_RECORD_INVALID",
            "event timestamp must be finite.",
        )
    if event.run_id is not None and (
        not isinstance(event.run_id, str)
        or not event.run_id
        or len(event.run_id) > 256
        or any(ord(char) < 32 or ord(char) == 127 for char in event.run_id)
    ):
        return _error(
            "EVENT_JOURNAL_RECORD_INVALID",
            "run_id must be bounded and contain no control characters.",
        )
    invalid_payload = _validate_event_value(event.payload)
    if invalid_payload is not None:
        return invalid_payload
    encoded = _json_size(event.as_dict())
    if encoded.is_err():
        return _error(
            "EVENT_JOURNAL_RECORD_INVALID",
            "event must be JSON serializable.",
        )
    return None


def _validate_event_search_filter(
    value: Any, field: str, max_length: int
) -> Optional[Error]:
    if (
        not isinstance(value, str)
        or not value
        or len(value) > max_length
        or any(ord(char) < 32 or ord(char) == 127 for char in value)
    ):
        return _error(
            "EVENT_SEARCH_INVALID",
            f"{field} must be bounded text when provided.",
        )
    return None


def _event_from_dict(value: Any) -> Result[AgentEvent, Error]:
    if not isinstance(value, Mapping):
        return Result.err(
            _error("EVENT_JOURNAL_RECORD_INVALID", "event record must be an object.")
        )
    required = ("sequence", "event_type", "timestamp", "payload", "run_id")
    if any(field not in value for field in required):
        return Result.err(
            _error(
                "EVENT_JOURNAL_RECORD_INVALID",
                "event record is missing a required field.",
            )
        )
    try:
        event = AgentEvent(
            sequence=value["sequence"],
            event_type=value["event_type"],
            timestamp=value["timestamp"],
            payload=value["payload"],
            run_id=value["run_id"],
        )
    except (TypeError, ValueError, OverflowError) as exc:
        return Result.err(
            _error(
                "EVENT_JOURNAL_RECORD_INVALID",
                "event record could not be constructed.",
                reason=type(exc).__name__,
            )
        )
    invalid = _validate_event_record(event)
    if invalid is not None:
        return Result.err(invalid)
    return Result.ok(event)


@dataclass(frozen=True)
class _EventDeduplicationRecord:
    fingerprint: str
    event: Optional[AgentEvent]
    expires_at: float


def _event_deduplication_fingerprint(event: AgentEvent) -> Result[str, Error]:
    """Return a stable digest without retaining the source payload."""
    try:
        encoded = json.dumps(
            {
                "event_type": event.event_type,
                "payload": event.payload,
                "run_id": event.run_id,
            },
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError, OverflowError):
        return Result.err(
            _error(
                "EVENT_DEDUPLICATION_INPUT_INVALID",
                "event identity is not JSON serializable.",
            )
        )
    return Result.ok(hashlib.sha256(encoded).hexdigest())


class InMemoryEventDeduplicationStore:
    """Bounded, process-local deduplication for authenticated event batches.

    The store keys claims by ``(source_id, source_sequence)`` and retains only
    a digest plus the already-redacted destination event. A claim is reserved
    before publication so concurrent duplicates fail closed while the first
    publication is in flight. Expiration and capacity eviction are deliberate;
    this is not durable deduplication or an exactly-once effects contract.
    """

    _MAX_ENTRIES = 100_000
    _MAX_TTL_SECONDS = 7 * 24 * 60 * 60.0

    def __init__(
        self,
        *,
        max_entries: int = DEFAULT_MAX_EVENT_DEDUP_ENTRIES,
        ttl_seconds: float = DEFAULT_EVENT_DEDUP_TTL_SECONDS,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        if (
            not isinstance(max_entries, int)
            or isinstance(max_entries, bool)
            or not 1 <= max_entries <= self._MAX_ENTRIES
        ):
            raise ValueError("max_entries must be between 1 and 100000")
        if (
            not isinstance(ttl_seconds, (int, float))
            or isinstance(ttl_seconds, bool)
            or not 0 < float(ttl_seconds) <= self._MAX_TTL_SECONDS
            or not math.isfinite(float(ttl_seconds))
        ):
            raise ValueError("ttl_seconds must be finite and within seven days")
        if not callable(clock):
            raise TypeError("clock must be callable")
        self.max_entries = max_entries
        self.ttl_seconds = float(ttl_seconds)
        self._clock = clock
        self._records: "OrderedDict[Tuple[str, int], _EventDeduplicationRecord]" = (
            OrderedDict()
        )
        self._lock = threading.RLock()

    @staticmethod
    def _validate_key(source_id: Any, source_sequence: Any) -> Optional[Error]:
        source_error = validate_event_source_id(source_id)
        if source_error is not None:
            return source_error
        if (
            not isinstance(source_sequence, int)
            or isinstance(source_sequence, bool)
            or source_sequence <= 0
        ):
            return _error(
                "EVENT_SOURCE_SEQUENCE_INVALID",
                "source_sequence must be a positive integer.",
            )
        return None

    def _purge_expired(self, now: float) -> None:
        expired = [
            key for key, record in self._records.items() if record.expires_at <= now
        ]
        for key in expired:
            self._records.pop(key, None)

    def claim(
        self,
        source_id: str,
        source_sequence: int,
        event: AgentEvent,
    ) -> Result[Optional[AgentEvent], Error]:
        """Reserve one source event or return its completed destination event."""
        key_error = self._validate_key(source_id, source_sequence)
        if key_error is not None:
            return Result.err(key_error)
        if not isinstance(event, AgentEvent) or event.sequence != source_sequence:
            return Result.err(
                _error(
                    "EVENT_DEDUPLICATION_INPUT_INVALID",
                    "event sequence must match source_sequence.",
                )
            )
        event_error = _validate_event_record(event)
        if event_error is not None:
            return Result.err(
                _error(
                    "EVENT_DEDUPLICATION_INPUT_INVALID",
                    "event is invalid for deduplication.",
                )
            )
        fingerprint_result = _event_deduplication_fingerprint(event)
        if fingerprint_result.is_err():
            return Result.err(fingerprint_result.unwrap_err())
        now = float(self._clock())
        if not math.isfinite(now):
            return Result.err(
                _error(
                    "EVENT_DEDUPLICATION_CLOCK_INVALID",
                    "deduplication clock is invalid.",
                )
            )
        key = (source_id, source_sequence)
        with self._lock:
            self._purge_expired(now)
            existing = self._records.get(key)
            if existing is not None:
                if existing.fingerprint != fingerprint_result.unwrap():
                    return Result.err(
                        _error(
                            "EVENT_DEDUPLICATION_CONFLICT",
                            (
                                "source sequence was previously claimed with "
                                "different content."
                            ),
                        )
                    )
                self._records.move_to_end(key)
                if existing.event is None:
                    return Result.err(
                        _error(
                            "EVENT_DEDUPLICATION_IN_PROGRESS",
                            "source sequence is currently being published.",
                        )
                    )
                return Result.ok(existing.event)
            while len(self._records) >= self.max_entries:
                self._records.popitem(last=False)
            self._records[key] = _EventDeduplicationRecord(
                fingerprint=fingerprint_result.unwrap(),
                event=None,
                expires_at=now + self.ttl_seconds,
            )
        return Result.ok(None)

    def complete(
        self, source_id: str, source_sequence: int, event: AgentEvent
    ) -> Result[AgentEvent, Error]:
        """Complete a claim with the redacted destination event."""
        key_error = self._validate_key(source_id, source_sequence)
        if key_error is not None:
            return Result.err(key_error)
        if not isinstance(event, AgentEvent):
            return Result.err(
                _error("EVENT_DEDUPLICATION_INPUT_INVALID", "event is invalid.")
            )
        event_error = _validate_event_record(event)
        if event_error is not None:
            return Result.err(
                _error(
                    "EVENT_DEDUPLICATION_INPUT_INVALID",
                    "destination event is invalid.",
                )
            )
        key = (source_id, source_sequence)
        now = float(self._clock())
        if not math.isfinite(now):
            return Result.err(
                _error(
                    "EVENT_DEDUPLICATION_CLOCK_INVALID",
                    "deduplication clock is invalid.",
                )
            )
        with self._lock:
            self._purge_expired(now)
            existing = self._records.get(key)
            if existing is None:
                return Result.err(
                    _error(
                        "EVENT_DEDUPLICATION_CLAIM_MISSING",
                        "event has no active deduplication claim.",
                    )
                )
            if existing.event is not None:
                return Result.ok(existing.event)
            completed = _EventDeduplicationRecord(
                fingerprint=existing.fingerprint,
                event=event,
                expires_at=existing.expires_at,
            )
            self._records[key] = completed
            self._records.move_to_end(key)
            return Result.ok(event)

    def abort(self, source_id: str, source_sequence: int) -> Result[None, Error]:
        """Release a pending claim without removing a completed event."""
        key_error = self._validate_key(source_id, source_sequence)
        if key_error is not None:
            return Result.err(key_error)
        key = (source_id, source_sequence)
        with self._lock:
            self._purge_expired(float(self._clock()))
            existing = self._records.get(key)
            if existing is not None and existing.event is None:
                self._records.pop(key, None)
        return Result.ok(None)

    def metrics(self) -> Dict[str, int]:
        """Return a bounded local record count without exposing payloads."""
        with self._lock:
            self._purge_expired(float(self._clock()))
            return {
                "retained_claims": len(self._records),
                "max_entries": self.max_entries,
            }


class FileEventDeduplicationStore:
    """Bounded durable deduplication for one local event receiver.

    The store persists only source identity, a content fingerprint, expiry,
    and the already-redacted destination event. A durable lease serializes
    local processes using the same directory. Expiry and bounded retention
    are deliberate; this remains an at-least-once replay guard rather than an
    exactly-once side-effect protocol.
    """

    _FILENAME = "deduplication.json"
    _TEMP_PREFIX = ".maple-event-deduplication-"
    _MAX_ENTRIES = 100_000
    _MAX_TTL_SECONDS = 7 * 24 * 60 * 60.0

    def __init__(
        self,
        directory: Union[str, Path],
        *,
        max_entries: int = DEFAULT_MAX_EVENT_DEDUP_ENTRIES,
        ttl_seconds: float = DEFAULT_EVENT_DEDUP_TTL_SECONDS,
        max_bytes: int = DEFAULT_MAX_EVENT_DEDUP_BYTES,
        lease_ttl_seconds: float = 30.0,
        clock: Callable[[], float] = time.time,
    ) -> None:
        if (
            not isinstance(max_entries, int)
            or isinstance(max_entries, bool)
            or not 1 <= max_entries <= self._MAX_ENTRIES
        ):
            raise ValueError("max_entries must be between 1 and 100000")
        if (
            not isinstance(ttl_seconds, (int, float))
            or isinstance(ttl_seconds, bool)
            or not 0 < float(ttl_seconds) <= self._MAX_TTL_SECONDS
            or not math.isfinite(float(ttl_seconds))
        ):
            raise ValueError("ttl_seconds must be finite and within seven days")
        if (
            not isinstance(max_bytes, int)
            or isinstance(max_bytes, bool)
            or not 1 <= max_bytes <= _MAX_EVENT_DEDUP_BYTES
        ):
            raise ValueError(
                f"max_bytes must be between 1 and {_MAX_EVENT_DEDUP_BYTES}"
            )
        if not callable(clock):
            raise TypeError("clock must be callable")
        self.max_entries = max_entries
        self.ttl_seconds = float(ttl_seconds)
        self.max_bytes = max_bytes
        self._clock = clock
        self.directory = Path(directory).expanduser().resolve()
        try:
            self.directory.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            raise ValueError("event deduplication directory is unavailable") from exc
        if not self.directory.is_dir():
            raise ValueError("event deduplication path must be a directory")
        self.path = self.directory / self._FILENAME
        self._lock = threading.RLock()
        try:
            self._lease = DurableRecordLease(
                self.directory,
                namespace="event-deduplication",
                holder_label="file-event-deduplication",
                lease_ttl_seconds=lease_ttl_seconds,
            )
        except (OSError, TypeError, ValueError) as exc:
            raise ValueError("event deduplication lease is unavailable") from exc

    @staticmethod
    def _valid_fingerprint(value: Any) -> bool:
        return (
            isinstance(value, str)
            and len(value) == 64
            and all(character in "0123456789abcdef" for character in value)
        )

    @staticmethod
    def _load_error(message: str) -> Error:
        return _error("EVENT_DEDUPLICATION_LOAD_ERROR", message)

    @staticmethod
    def _save_error(message: str, **details: Any) -> Error:
        return _error("EVENT_DEDUPLICATION_SAVE_ERROR", message, **details)

    def _now(self) -> Result[float, Error]:
        try:
            now = float(self._clock())
        except (OverflowError, TypeError, ValueError):
            return Result.err(
                _error(
                    "EVENT_DEDUPLICATION_CLOCK_INVALID",
                    "deduplication clock is invalid.",
                )
            )
        if not math.isfinite(now):
            return Result.err(
                _error(
                    "EVENT_DEDUPLICATION_CLOCK_INVALID",
                    "deduplication clock is invalid.",
                )
            )
        return Result.ok(now)

    @staticmethod
    def _record_to_dict(
        key: Tuple[str, int], record: _EventDeduplicationRecord
    ) -> Dict[str, Any]:
        return {
            "source_id": key[0],
            "source_sequence": key[1],
            "fingerprint": record.fingerprint,
            "event": record.event.as_dict() if record.event is not None else None,
            "expires_at": record.expires_at,
        }

    def _read_unlocked(
        self,
    ) -> Result["OrderedDict[Tuple[str, int], _EventDeduplicationRecord]", Error]:
        records: "OrderedDict[Tuple[str, int], _EventDeduplicationRecord]" = (
            OrderedDict()
        )
        if not self.path.exists():
            return Result.ok(records)
        try:
            if self.path.stat().st_size > self.max_bytes:
                return Result.err(
                    self._load_error(
                        "event deduplication state exceeds the byte limit."
                    )
                )
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, TypeError, ValueError, json.JSONDecodeError):
            return Result.err(
                self._load_error("event deduplication state could not be loaded.")
            )
        if (
            not isinstance(data, Mapping)
            or data.get("version") != _EVENT_DEDUPLICATION_VERSION
            or not isinstance(data.get("records"), list)
            or len(data["records"]) > self.max_entries
        ):
            return Result.err(self._load_error("event deduplication state is invalid."))
        for raw_record in data["records"]:
            if not isinstance(raw_record, Mapping):
                return Result.err(self._load_error("deduplication record is invalid."))
            source_id = raw_record.get("source_id")
            source_sequence = raw_record.get("source_sequence")
            if not isinstance(source_id, str) or validate_event_source_id(source_id):
                return Result.err(
                    self._load_error("deduplication record identity is invalid.")
                )
            if (
                not isinstance(source_sequence, int)
                or isinstance(source_sequence, bool)
                or source_sequence <= 0
            ):
                return Result.err(
                    self._load_error("deduplication record identity is invalid.")
                )
            key = (source_id, source_sequence)
            if key in records:
                return Result.err(
                    self._load_error(
                        "deduplication state contains duplicate identities."
                    )
                )
            fingerprint = raw_record.get("fingerprint")
            if not isinstance(fingerprint, str) or not self._valid_fingerprint(
                fingerprint
            ):
                return Result.err(
                    self._load_error("deduplication fingerprint is invalid.")
                )
            expires_at = raw_record.get("expires_at")
            if (
                not isinstance(expires_at, (int, float))
                or isinstance(expires_at, bool)
                or not math.isfinite(float(expires_at))
            ):
                return Result.err(self._load_error("deduplication expiry is invalid."))
            raw_event = raw_record.get("event")
            event: Optional[AgentEvent] = None
            if raw_event is not None:
                parsed = _event_from_dict(raw_event)
                if parsed.is_err():
                    return Result.err(
                        self._load_error("deduplication event is invalid.")
                    )
                event = parsed.unwrap()
            records[key] = _EventDeduplicationRecord(
                fingerprint=fingerprint,
                event=event,
                expires_at=float(expires_at),
            )
        encoded = self._encode(records)
        if encoded.is_err():
            return Result.err(
                self._load_error("deduplication state exceeds its limits.")
            )
        return Result.ok(records)

    def _encode(
        self,
        records: "OrderedDict[Tuple[str, int], _EventDeduplicationRecord]",
    ) -> Result[str, Error]:
        if len(records) > self.max_entries:
            return Result.err(
                _error(
                    "EVENT_DEDUPLICATION_CAPACITY",
                    "event deduplication entry limit reached.",
                    max_entries=self.max_entries,
                )
            )
        try:
            encoded = json.dumps(
                {
                    "version": _EVENT_DEDUPLICATION_VERSION,
                    "records": [
                        self._record_to_dict(key, record)
                        for key, record in records.items()
                    ],
                },
                ensure_ascii=False,
                allow_nan=False,
                separators=(",", ":"),
            )
        except (TypeError, ValueError, OverflowError):
            return Result.err(
                self._save_error("event deduplication state is not serializable.")
            )
        if len(encoded.encode("utf-8")) > self.max_bytes:
            return Result.err(
                _error(
                    "EVENT_DEDUPLICATION_SIZE",
                    "event deduplication state exceeds the byte limit.",
                    max_bytes=self.max_bytes,
                )
            )
        return Result.ok(encoded)

    def _write_unlocked(
        self,
        records: "OrderedDict[Tuple[str, int], _EventDeduplicationRecord]",
    ) -> Result[None, Error]:
        encoded = self._encode(records)
        if encoded.is_err():
            return Result.err(encoded.unwrap_err())
        temporary_path: Optional[Path] = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                dir=str(self.directory),
                prefix=self._TEMP_PREFIX,
                suffix=".tmp",
                delete=False,
            ) as handle:
                temporary_path = Path(handle.name)
                handle.write(encoded.unwrap())
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(str(temporary_path), str(self.path))
            temporary_path = None
            return Result.ok(None)
        except (OSError, TypeError, ValueError) as exc:
            return Result.err(
                self._save_error(
                    "event deduplication state could not be saved.",
                    reason=type(exc).__name__,
                )
            )
        finally:
            if temporary_path is not None:
                try:
                    temporary_path.unlink()
                except OSError:
                    pass

    @staticmethod
    def _purge_expired(
        records: "OrderedDict[Tuple[str, int], _EventDeduplicationRecord]",
        now: float,
    ) -> bool:
        expired = [key for key, record in records.items() if record.expires_at <= now]
        for key in expired:
            records.pop(key, None)
        return bool(expired)

    def _run(
        self,
        operation: str,
        callback: Callable[[], Result[Any, Error]],
    ) -> Result[Any, Error]:
        try:
            return self._lease.run(
                "store",
                operation,
                callback,
                acquire_error_type="EVENT_DEDUPLICATION_LEASE_ERROR",
                acquire_error_message=(
                    "event deduplication lease could not be acquired."
                ),
                release_error_type="EVENT_DEDUPLICATION_LEASE_RELEASE_ERROR",
                release_error_message=(
                    "event deduplication lease could not be released."
                ),
            )
        except Exception as exc:
            return Result.err(
                _error(
                    "EVENT_DEDUPLICATION_ERROR",
                    "event deduplication operation failed.",
                    operation=operation,
                    reason=type(exc).__name__,
                )
            )

    def claim(
        self,
        source_id: str,
        source_sequence: int,
        event: AgentEvent,
    ) -> Result[Optional[AgentEvent], Error]:
        """Durably reserve a source event or return its copied destination."""
        key_error = InMemoryEventDeduplicationStore._validate_key(
            source_id, source_sequence
        )
        if key_error is not None:
            return Result.err(key_error)
        if not isinstance(event, AgentEvent) or event.sequence != source_sequence:
            return Result.err(
                _error(
                    "EVENT_DEDUPLICATION_INPUT_INVALID",
                    "event sequence must match source_sequence.",
                )
            )
        event_error = _validate_event_record(event)
        if event_error is not None:
            return Result.err(
                _error(
                    "EVENT_DEDUPLICATION_INPUT_INVALID",
                    "event is invalid for deduplication.",
                )
            )
        fingerprint_result = _event_deduplication_fingerprint(event)
        if fingerprint_result.is_err():
            return Result.err(fingerprint_result.unwrap_err())
        fingerprint = fingerprint_result.unwrap()
        key = (source_id, source_sequence)

        def operation() -> Result[Optional[AgentEvent], Error]:
            now_result = self._now()
            if now_result.is_err():
                return Result.err(now_result.unwrap_err())
            current = self._read_unlocked()
            if current.is_err():
                return Result.err(current.unwrap_err())
            records = current.unwrap()
            self._purge_expired(records, now_result.unwrap())
            existing = records.get(key)
            if existing is not None:
                if existing.fingerprint != fingerprint:
                    return Result.err(
                        _error(
                            "EVENT_DEDUPLICATION_CONFLICT",
                            (
                                "source sequence was previously claimed with "
                                "different content."
                            ),
                        )
                    )
                if existing.event is None:
                    return Result.err(
                        _error(
                            "EVENT_DEDUPLICATION_IN_PROGRESS",
                            "source sequence is currently being published.",
                        )
                    )
                return Result.ok(_event_from_dict(existing.event.as_dict()).unwrap())
            if len(records) >= self.max_entries:
                evictable = next(
                    (
                        candidate_key
                        for candidate_key, candidate in records.items()
                        if candidate.event is not None
                    ),
                    None,
                )
                if evictable is None:
                    return Result.err(
                        _error(
                            "EVENT_DEDUPLICATION_CAPACITY",
                            (
                                "event deduplication has no completed claim "
                                "available for eviction."
                            ),
                            max_entries=self.max_entries,
                        )
                    )
                records.pop(evictable, None)
            expires_at = now_result.unwrap() + self.ttl_seconds
            if not math.isfinite(expires_at):
                return Result.err(
                    _error(
                        "EVENT_DEDUPLICATION_CLOCK_INVALID",
                        "deduplication expiry is invalid.",
                    )
                )
            records[key] = _EventDeduplicationRecord(
                fingerprint=fingerprint,
                event=None,
                expires_at=expires_at,
            )
            saved = self._write_unlocked(records)
            if saved.is_err():
                return Result.err(saved.unwrap_err())
            return Result.ok(None)

        with self._lock:
            result = self._run("claim", operation)
        return (
            Result.err(result.unwrap_err())
            if result.is_err()
            else Result.ok(result.unwrap())
        )

    def complete(
        self, source_id: str, source_sequence: int, event: AgentEvent
    ) -> Result[AgentEvent, Error]:
        """Durably complete a claim with a copied destination event."""
        key_error = InMemoryEventDeduplicationStore._validate_key(
            source_id, source_sequence
        )
        if key_error is not None:
            return Result.err(key_error)
        if not isinstance(event, AgentEvent):
            return Result.err(
                _error("EVENT_DEDUPLICATION_INPUT_INVALID", "event is invalid.")
            )
        event_error = _validate_event_record(event)
        if event_error is not None:
            return Result.err(
                _error(
                    "EVENT_DEDUPLICATION_INPUT_INVALID",
                    "destination event is invalid.",
                )
            )
        copied_event_result = _event_from_dict(event.as_dict())
        if copied_event_result.is_err():
            return Result.err(
                _error(
                    "EVENT_DEDUPLICATION_INPUT_INVALID",
                    "destination event is invalid.",
                )
            )
        copied_event = copied_event_result.unwrap()
        key = (source_id, source_sequence)

        def operation() -> Result[AgentEvent, Error]:
            now_result = self._now()
            if now_result.is_err():
                return Result.err(now_result.unwrap_err())
            current = self._read_unlocked()
            if current.is_err():
                return Result.err(current.unwrap_err())
            records = current.unwrap()
            purged = self._purge_expired(records, now_result.unwrap())
            existing = records.get(key)
            if existing is None:
                if purged:
                    saved = self._write_unlocked(records)
                    if saved.is_err():
                        return Result.err(saved.unwrap_err())
                return Result.err(
                    _error(
                        "EVENT_DEDUPLICATION_CLAIM_MISSING",
                        "event has no active deduplication claim.",
                    )
                )
            if existing.event is not None:
                return Result.ok(_event_from_dict(existing.event.as_dict()).unwrap())
            records[key] = _EventDeduplicationRecord(
                fingerprint=existing.fingerprint,
                event=copied_event,
                expires_at=existing.expires_at,
            )
            saved = self._write_unlocked(records)
            if saved.is_err():
                return Result.err(saved.unwrap_err())
            return Result.ok(_event_from_dict(copied_event.as_dict()).unwrap())

        with self._lock:
            result = self._run("complete", operation)
        return (
            Result.err(result.unwrap_err())
            if result.is_err()
            else Result.ok(result.unwrap())
        )

    def abort(self, source_id: str, source_sequence: int) -> Result[None, Error]:
        """Durably release a pending claim without removing a completed event."""
        key_error = InMemoryEventDeduplicationStore._validate_key(
            source_id, source_sequence
        )
        if key_error is not None:
            return Result.err(key_error)
        key = (source_id, source_sequence)

        def operation() -> Result[None, Error]:
            now_result = self._now()
            if now_result.is_err():
                return Result.err(now_result.unwrap_err())
            current = self._read_unlocked()
            if current.is_err():
                return Result.err(current.unwrap_err())
            records = current.unwrap()
            changed = self._purge_expired(records, now_result.unwrap())
            existing = records.get(key)
            if existing is not None and existing.event is None:
                records.pop(key, None)
                changed = True
            if changed:
                saved = self._write_unlocked(records)
                if saved.is_err():
                    return Result.err(saved.unwrap_err())
            return Result.ok(None)

        with self._lock:
            result = self._run("abort", operation)
        return Result.err(result.unwrap_err()) if result.is_err() else Result.ok(None)


class FileEventJournal:
    """Atomic, bounded JSON event journal for local process restarts."""

    _FILENAME = "events.json"
    _TEMP_PREFIX = ".maple-events-"

    def __init__(
        self,
        directory: Union[str, Path],
        *,
        max_events: int = 1_000,
        max_bytes: int = DEFAULT_MAX_JOURNAL_BYTES,
        lease_ttl_seconds: float = 30.0,
    ) -> None:
        if (
            not isinstance(max_events, int)
            or isinstance(max_events, bool)
            or max_events <= 0
        ):
            raise ValueError("max_events must be a positive integer")
        if (
            not isinstance(max_bytes, int)
            or isinstance(max_bytes, bool)
            or max_bytes <= 0
        ):
            raise ValueError("max_bytes must be a positive integer")
        self.max_events = max_events
        self.max_bytes = max_bytes
        self.directory = Path(directory)
        try:
            self.directory.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            raise ValueError("event journal directory is unavailable") from exc
        if not self.directory.is_dir():
            raise ValueError("event journal path must be a directory")
        self.path = self.directory / self._FILENAME
        self._lock = threading.RLock()
        try:
            self._lease = DurableRecordLease(
                self.directory,
                namespace="event-journal",
                holder_label="file-event-journal",
                lease_ttl_seconds=lease_ttl_seconds,
            )
        except (OSError, TypeError, ValueError) as exc:
            raise ValueError("event journal lease is unavailable") from exc

    def _read_unlocked(self) -> Result[List[AgentEvent], Error]:
        if not self.path.exists():
            return Result.ok([])
        try:
            if self.path.stat().st_size > self.max_bytes:
                return Result.err(
                    _error(
                        "EVENT_JOURNAL_LOAD_ERROR",
                        "event journal exceeds the byte limit.",
                    )
                )
            data = json.loads(self.path.read_text(encoding="utf-8"))
            version = data.get("version") if isinstance(data, Mapping) else None
            if (
                not isinstance(data, Mapping)
                or not isinstance(version, int)
                or isinstance(version, bool)
                or version != _EVENT_JOURNAL_VERSION
            ):
                return Result.err(
                    _error(
                        "EVENT_JOURNAL_LOAD_ERROR",
                        "event journal version is unsupported.",
                    )
                )
            raw_events = data.get("events")
            if not isinstance(raw_events, list) or len(raw_events) > self.max_events:
                return Result.err(
                    _error(
                        "EVENT_JOURNAL_LOAD_ERROR",
                        "event journal event count is invalid.",
                    )
                )
            events: List[AgentEvent] = []
            for raw_event in raw_events:
                parsed = _event_from_dict(raw_event)
                if parsed.is_err():
                    return Result.err(
                        _error(
                            "EVENT_JOURNAL_LOAD_ERROR",
                            "event journal contains an invalid event.",
                        )
                    )
                event = parsed.unwrap()
                if events and event.sequence <= events[-1].sequence:
                    return Result.err(
                        _error(
                            "EVENT_JOURNAL_LOAD_ERROR",
                            "event journal sequences are not strictly increasing.",
                        )
                    )
                events.append(event)
            encoded = self._encode(events)
            if encoded.is_err():
                return Result.err(
                    _error(
                        "EVENT_JOURNAL_LOAD_ERROR",
                        "event journal content exceeds the byte limit.",
                    )
                )
            return Result.ok(events)
        except (OSError, TypeError, ValueError, OverflowError, json.JSONDecodeError):
            return Result.err(
                _error(
                    "EVENT_JOURNAL_LOAD_ERROR",
                    "event journal could not be loaded.",
                )
            )

    def _encode(self, events: List[AgentEvent]) -> Result[str, Error]:
        try:
            encoded = json.dumps(
                {
                    "version": _EVENT_JOURNAL_VERSION,
                    "events": [event.as_dict() for event in events],
                },
                ensure_ascii=False,
                allow_nan=False,
                separators=(",", ":"),
            )
        except (TypeError, ValueError, OverflowError):
            return Result.err(
                _error(
                    "EVENT_JOURNAL_RECORD_INVALID",
                    "event journal content is not JSON serializable.",
                )
            )
        if len(encoded.encode("utf-8")) > self.max_bytes:
            return Result.err(
                _error(
                    "EVENT_JOURNAL_SIZE",
                    "event journal exceeds the byte limit.",
                    max_bytes=self.max_bytes,
                )
            )
        return Result.ok(encoded)

    def _write_unlocked(self, events: List[AgentEvent]) -> Result[AgentEvent, Error]:
        encoded = self._encode(events)
        if encoded.is_err():
            return Result.err(encoded.unwrap_err())
        temporary_path: Optional[Path] = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                dir=str(self.directory),
                prefix=self._TEMP_PREFIX,
                suffix=".tmp",
                delete=False,
            ) as handle:
                temporary_path = Path(handle.name)
                handle.write(encoded.unwrap())
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(str(temporary_path), str(self.path))
            temporary_path = None
            return Result.ok(events[-1])
        except (OSError, TypeError, ValueError) as exc:
            return Result.err(
                _error(
                    "EVENT_JOURNAL_SAVE_ERROR",
                    "event journal could not be saved.",
                    reason=type(exc).__name__,
                )
            )
        finally:
            if temporary_path is not None:
                try:
                    temporary_path.unlink()
                except OSError:
                    pass

    def _run(
        self,
        operation: str,
        callback: Callable[[], Result[Any, Error]],
    ) -> Result[Any, Error]:
        try:
            return self._lease.run(
                "stream",
                operation,
                callback,
                acquire_error_type="EVENT_JOURNAL_LEASE_ERROR",
                acquire_error_message="event journal lease could not be acquired.",
                release_error_type="EVENT_JOURNAL_LEASE_RELEASE_ERROR",
                release_error_message="event journal lease could not be released.",
            )
        except Exception as exc:
            return Result.err(
                _error(
                    "EVENT_JOURNAL_ERROR",
                    "event journal operation failed.",
                    operation=operation,
                    reason=type(exc).__name__,
                )
            )

    def load(self) -> Result[List[AgentEvent], Error]:
        """Load the bounded retained event window."""
        with self._lock:
            result = self._run("load", self._read_unlocked)
        if result.is_err():
            return Result.err(result.unwrap_err())
        return Result.ok(result.unwrap())

    def append(self, event: AgentEvent) -> Result[AgentEvent, Error]:
        """Persist one event with monotonic sequence and bounded retention."""
        invalid = _validate_event_record(event)
        if invalid is not None:
            return Result.err(invalid)

        def operation() -> Result[AgentEvent, Error]:
            current = self._read_unlocked()
            if current.is_err():
                return Result.err(current.unwrap_err())
            events = current.unwrap()
            if events and event.sequence <= events[-1].sequence:
                return Result.err(
                    _error(
                        "EVENT_JOURNAL_CONFLICT",
                        "event sequence is not newer than the journal tail.",
                        event_sequence=event.sequence,
                        latest_sequence=events[-1].sequence,
                    )
                )
            retained = (events + [event])[-self.max_events :]
            return self._write_unlocked(retained)

        with self._lock:
            result = self._run("append", operation)
        if result.is_err():
            return Result.err(result.unwrap_err())
        return Result.ok(result.unwrap())


class EventStream:
    """Thread-safe bounded event stream with redacted callbacks and journaling."""

    def __init__(
        self,
        *,
        max_events: int = 1_000,
        max_payload_bytes: int = 1_048_576,
        max_subscribers: int = 1_000,
        redaction: Optional[RedactionPolicy] = None,
        exporter: Optional[EventExporter] = None,
        journal: Optional[EventJournal] = None,
    ) -> None:
        self.max_events = max_events
        self.max_payload_bytes = max_payload_bytes
        self.max_subscribers = max_subscribers
        self.redaction = redaction or RedactionPolicy()
        self.exporter = exporter
        self.journal = journal
        event_capacity = (
            max_events
            if isinstance(max_events, int)
            and not isinstance(max_events, bool)
            and max_events > 0
            else 1
        )
        self._events: Deque[AgentEvent] = deque(maxlen=event_capacity)
        self._callbacks: Dict[int, EventCallback] = {}
        self._next_sequence = 1
        self._next_subscription = 1
        self._dropped = 0
        self._published = 0
        self._subscriber_failures = 0
        self._exporter_failures = 0
        self._journal_failures = 0
        self._publish_latency_total_ms = 0
        self._publish_latency_max_ms = 0
        self._publish_latency_samples: Deque[int] = deque(
            maxlen=min(event_capacity, _MAX_LATENCY_SAMPLES)
        )
        self._condition = threading.Condition(threading.RLock())
        self._publish_lock = threading.Lock()
        if self.journal is not None:
            journal_load = getattr(self.journal, "load", None)
            journal_append = getattr(self.journal, "append", None)
            if not callable(journal_load) or not callable(journal_append):
                raise ValueError("journal must expose load() and append(event)")
            journal_max_events = getattr(self.journal, "max_events", None)
            if journal_max_events is not None and journal_max_events != max_events:
                raise ValueError("journal max_events must match stream max_events")
            config_error = self._validate_config()
            if config_error is not None:
                raise ValueError(config_error["message"])
            try:
                loaded = self.journal.load()
            except Exception as exc:
                raise ValueError("event journal could not be loaded") from exc
            if loaded.is_err():
                raise ValueError("event journal could not be loaded")
            self._hydrate(loaded.unwrap())

    def _hydrate(self, loaded: Any) -> None:
        if not isinstance(loaded, (list, tuple)) or len(loaded) > self.max_events:
            raise ValueError("event journal returned an invalid event window")
        hydrated: List[AgentEvent] = []
        for event in loaded:
            invalid = _validate_event_record(event)
            if invalid is not None:
                raise ValueError("event journal returned an invalid event")
            if hydrated and event.sequence <= hydrated[-1].sequence:
                raise ValueError("event journal returned non-monotonic events")
            redacted = self.redaction.redact(event.payload)
            if redacted.is_err():
                raise ValueError("event journal payload failed redaction")
            size = _json_size(redacted.unwrap())
            if size.is_err() or size.unwrap() > self.max_payload_bytes:
                raise ValueError("event journal payload exceeds stream limits")
            hydrated.append(replace(event, payload=redacted.unwrap()))
        with self._condition:
            self._events.extend(hydrated)
            if hydrated:
                self._next_sequence = hydrated[-1].sequence + 1

    def _validate_config(self) -> Optional[Error]:
        if (
            not isinstance(self.max_events, int)
            or isinstance(self.max_events, bool)
            or self.max_events <= 0
        ):
            return _error("EVENT_CONFIG_INVALID", "max_events must be positive.")
        if (
            not isinstance(self.max_payload_bytes, int)
            or isinstance(self.max_payload_bytes, bool)
            or self.max_payload_bytes <= 0
        ):
            return _error("EVENT_CONFIG_INVALID", "max_payload_bytes must be positive.")
        if (
            not isinstance(self.max_subscribers, int)
            or isinstance(self.max_subscribers, bool)
            or self.max_subscribers <= 0
        ):
            return _error("EVENT_CONFIG_INVALID", "max_subscribers must be positive.")
        if self.exporter is not None and not callable(
            getattr(self.exporter, "export", None)
        ):
            return _error("EVENT_CONFIG_INVALID", "exporter must expose export(event).")
        if self.journal is not None and (
            not callable(getattr(self.journal, "load", None))
            or not callable(getattr(self.journal, "append", None))
        ):
            return _error(
                "EVENT_CONFIG_INVALID",
                "journal must expose load() and append(event).",
            )
        return self.redaction.validate()

    def publish(
        self,
        event_type: str,
        payload: Any,
        *,
        run_id: Optional[str] = None,
    ) -> Result[AgentEvent, Error]:
        """Redact, bound, retain, and deliver one event."""
        publish_started = time.perf_counter()
        config_error = self._validate_config()
        if config_error is not None:
            return Result.err(config_error)
        if not isinstance(event_type, str) or not event_type or len(event_type) > 128:
            return Result.err(
                _error(
                    "EVENT_INPUT_INVALID", "event_type must be bounded and non-empty."
                )
            )
        if any(ord(char) < 32 or ord(char) == 127 for char in event_type):
            return Result.err(
                _error(
                    "EVENT_INPUT_INVALID",
                    "event_type must not contain control characters.",
                )
            )
        if run_id is not None and (
            not isinstance(run_id, str) or not run_id or len(run_id) > 256
        ):
            return Result.err(
                _error("EVENT_INPUT_INVALID", "run_id must be bounded when provided.")
            )
        if run_id is not None and any(
            ord(char) < 32 or ord(char) == 127 for char in run_id
        ):
            return Result.err(
                _error(
                    "EVENT_INPUT_INVALID", "run_id must not contain control characters."
                )
            )
        redacted = self.redaction.redact(payload)
        if redacted.is_err():
            return Result.err(redacted.unwrap_err())
        size = _json_size(redacted.unwrap())
        if size.is_err():
            return Result.err(size.unwrap_err())
        if size.unwrap() > self.max_payload_bytes:
            return Result.err(
                _error(
                    "EVENT_PAYLOAD_TOO_LARGE", "event payload exceeds the byte limit."
                )
            )

        callbacks: List[EventCallback]
        with self._publish_lock:
            with self._condition:
                event = AgentEvent(
                    sequence=self._next_sequence,
                    event_type=event_type,
                    timestamp=time.time(),
                    payload=redacted.unwrap(),
                    run_id=run_id,
                )
            if self.journal is not None:
                try:
                    persisted = self.journal.append(event)
                    if persisted.is_err():
                        with self._condition:
                            self._journal_failures += 1
                        return Result.err(persisted.unwrap_err())
                    if persisted.unwrap() != event:
                        with self._condition:
                            self._journal_failures += 1
                        return Result.err(
                            _error(
                                "EVENT_JOURNAL_CONFLICT",
                                "event journal returned a different event.",
                            )
                        )
                except Exception as exc:
                    with self._condition:
                        self._journal_failures += 1
                    return Result.err(
                        _error(
                            "EVENT_JOURNAL_ERROR",
                            "event journal append failed.",
                            reason=type(exc).__name__,
                        )
                    )
            with self._condition:
                if len(self._events) == self.max_events:
                    self._dropped += 1
                self._next_sequence += 1
                self._events.append(event)
                callbacks = list(self._callbacks.values())
                self._published += 1
                self._condition.notify_all()
        for callback in callbacks:
            try:
                callback(event)
            except Exception:
                with self._condition:
                    self._subscriber_failures += 1
                continue
        if self.exporter is not None:
            try:
                self.exporter.export(event)
            except Exception:
                # Export is an observability side effect and must not fail a run.
                with self._condition:
                    self._exporter_failures += 1
        publish_latency_ms = max(
            0, int(round((time.perf_counter() - publish_started) * 1000))
        )
        with self._condition:
            self._publish_latency_total_ms += publish_latency_ms
            self._publish_latency_max_ms = max(
                self._publish_latency_max_ms, publish_latency_ms
            )
            self._publish_latency_samples.append(publish_latency_ms)
        return Result.ok(event)

    def snapshot(
        self, *, after_sequence: int = 0, limit: Optional[int] = None
    ) -> Result[List[AgentEvent], Error]:
        """Return retained events after a sequence number."""
        if (
            not isinstance(after_sequence, int)
            or isinstance(after_sequence, bool)
            or after_sequence < 0
        ):
            return Result.err(
                _error("EVENT_QUERY_INVALID", "after_sequence must be non-negative.")
            )
        if limit is not None and (
            not isinstance(limit, int) or isinstance(limit, bool) or limit <= 0
        ):
            return Result.err(
                _error("EVENT_QUERY_INVALID", "limit must be positive when provided.")
            )
        with self._condition:
            events = [
                event for event in self._events if event.sequence > after_sequence
            ]
        if limit is not None:
            events = events[:limit]
        return Result.ok(events)

    def search(
        self,
        *,
        trace_id: Optional[str] = None,
        run_id: Optional[str] = None,
        event_type: Optional[str] = None,
        after_sequence: int = 0,
        limit: Optional[int] = None,
    ) -> Result[EventBatch, Error]:
        """Search retained redacted events with exact bounded filters.

        ``trace_id`` is matched only against a top-level value in the already
        redacted event payload. Search is a retained-window diagnostic seam;
        it does not query unretained or remote event storage.
        """
        if trace_id is None and run_id is None and event_type is None:
            return Result.err(
                _error(
                    "EVENT_SEARCH_INVALID",
                    "at least one search filter is required.",
                )
            )
        for value, field, max_length in (
            (trace_id, "trace_id", 128),
            (run_id, "run_id", 256),
            (event_type, "event_type", 128),
        ):
            if value is not None:
                invalid = _validate_event_search_filter(value, field, max_length)
                if invalid is not None:
                    return Result.err(invalid)
        if (
            not isinstance(after_sequence, int)
            or isinstance(after_sequence, bool)
            or after_sequence < 0
        ):
            return Result.err(
                _error(
                    "EVENT_SEARCH_INVALID",
                    "after_sequence must be non-negative.",
                )
            )
        max_limit = min(self.max_events, DEFAULT_MAX_EVENT_SEARCH_LIMIT)
        effective_limit = max_limit if limit is None else limit
        if (
            not isinstance(effective_limit, int)
            or isinstance(effective_limit, bool)
            or not 0 < effective_limit <= max_limit
        ):
            return Result.err(
                _error(
                    "EVENT_SEARCH_INVALID",
                    "limit must be positive and within the search bound.",
                    max_limit=max_limit,
                )
            )
        with self._condition:
            retained = list(self._events)
            oldest = retained[0].sequence if retained else None
            latest = retained[-1].sequence if retained else None
            if oldest is not None and after_sequence < oldest - 1:
                return Result.err(
                    _error(
                        "EVENT_CURSOR_EXPIRED",
                        "search cursor precedes the retained event window.",
                        cursor_sequence=after_sequence,
                        oldest_sequence=oldest,
                        latest_sequence=latest,
                    )
                )
            matches = []
            for event in retained:
                if event.sequence <= after_sequence:
                    continue
                if run_id is not None and event.run_id != run_id:
                    continue
                if event_type is not None and event.event_type != event_type:
                    continue
                if trace_id is not None and (
                    not isinstance(event.payload, Mapping)
                    or event.payload.get("trace_id") != trace_id
                ):
                    continue
                matches.append(event)
                if len(matches) == effective_limit:
                    break
        next_sequence = matches[-1].sequence if matches else after_sequence
        return Result.ok(
            EventBatch(
                events=tuple(matches),
                next_cursor=EventCursor(sequence=next_sequence),
                oldest_sequence=oldest,
                latest_sequence=latest,
            )
        )

    def read(
        self,
        cursor: Optional[EventCursor] = None,
        *,
        limit: Optional[int] = None,
    ) -> Result[EventBatch, Error]:
        """Read retained events from a cursor with explicit eviction detection.

        A cursor that points before the retained ring is rejected instead of
        silently skipping events. Callers may explicitly recover by starting
        from the returned ``oldest_sequence - 1`` position.
        """
        if cursor is None:
            cursor = EventCursor()
        if not isinstance(cursor, EventCursor):
            return Result.err(_error("EVENT_CURSOR_INVALID", "cursor is invalid."))
        effective_limit = self.max_events if limit is None else limit
        if (
            not isinstance(effective_limit, int)
            or isinstance(effective_limit, bool)
            or effective_limit <= 0
            or effective_limit > self.max_events
        ):
            return Result.err(
                _error(
                    "EVENT_QUERY_INVALID",
                    "limit must be positive and no greater than max_events.",
                )
            )
        with self._condition:
            retained = list(self._events)
            oldest = retained[0].sequence if retained else None
            latest = retained[-1].sequence if retained else None
            if oldest is not None and cursor.sequence < oldest - 1:
                return Result.err(
                    _error(
                        "EVENT_CURSOR_EXPIRED",
                        "cursor precedes the retained event window.",
                        cursor_sequence=cursor.sequence,
                        oldest_sequence=oldest,
                        latest_sequence=latest,
                    )
                )
            events = tuple(
                event for event in retained if event.sequence > cursor.sequence
            )[:effective_limit]
        next_sequence = events[-1].sequence if events else cursor.sequence
        return Result.ok(
            EventBatch(
                events=events,
                next_cursor=EventCursor(sequence=next_sequence),
                oldest_sequence=oldest,
                latest_sequence=latest,
            )
        )

    def wait_for(
        self,
        after_sequence: int,
        timeout: Optional[float] = None,
        *,
        cancellation: Optional[CancellationSignal] = None,
    ) -> Result[List[AgentEvent], Error]:
        """Wait until an event after ``after_sequence`` is retained."""
        if (
            not isinstance(after_sequence, int)
            or isinstance(after_sequence, bool)
            or after_sequence < 0
        ):
            return Result.err(
                _error("EVENT_QUERY_INVALID", "after_sequence must be non-negative.")
            )
        if timeout is not None and (
            not isinstance(timeout, (int, float))
            or isinstance(timeout, bool)
            or timeout < 0
        ):
            return Result.err(
                _error("EVENT_QUERY_INVALID", "timeout must be non-negative.")
            )
        if cancellation is not None and not callable(
            getattr(cancellation, "is_cancelled", None)
        ):
            return Result.err(
                _error(
                    "EVENT_CANCELLATION_INVALID",
                    "cancellation must expose is_cancelled().",
                )
            )

        def is_cancelled() -> Result[bool, Error]:
            if cancellation is None:
                return Result.ok(False)
            try:
                value = cancellation.is_cancelled()
            except Exception:
                return Result.err(
                    _error(
                        "EVENT_CANCELLATION_ERROR",
                        "cancellation state could not be read.",
                    )
                )
            if not isinstance(value, bool):
                return Result.err(
                    _error(
                        "EVENT_CANCELLATION_INVALID",
                        "is_cancelled() must return a boolean.",
                    )
                )
            return Result.ok(value)

        cancelled = is_cancelled()
        if cancelled.is_err():
            return Result.err(cancelled.unwrap_err())
        if cancelled.unwrap():
            return Result.err(_error("EVENT_CANCELLED", "event wait was cancelled."))
        deadline = None if timeout is None else time.monotonic() + timeout
        with self._condition:
            while not any(event.sequence > after_sequence for event in self._events):
                cancelled = is_cancelled()
                if cancelled.is_err():
                    return Result.err(cancelled.unwrap_err())
                if cancelled.unwrap():
                    return Result.err(
                        _error("EVENT_CANCELLED", "event wait was cancelled.")
                    )
                remaining = None if deadline is None else deadline - time.monotonic()
                if remaining is not None and remaining <= 0:
                    return Result.err(
                        _error("EVENT_WAIT_TIMEOUT", "no event arrived before timeout.")
                    )
                self._condition.wait(0.05 if cancellation is not None else remaining)
            return Result.ok(
                [event for event in self._events if event.sequence > after_sequence]
            )

    def subscribe(self, callback: EventCallback) -> Result[int, Error]:
        """Register a synchronous callback and return its subscription ID."""
        if not callable(callback):
            return Result.err(
                _error("EVENT_SUBSCRIBER_INVALID", "callback must be callable.")
            )
        with self._condition:
            if len(self._callbacks) >= self.max_subscribers:
                return Result.err(
                    _error("EVENT_SUBSCRIBER_LIMIT", "subscriber limit reached.")
                )
            subscription_id = self._next_subscription
            self._next_subscription += 1
            self._callbacks[subscription_id] = callback
        return Result.ok(subscription_id)

    def unsubscribe(self, subscription_id: int) -> Result[bool, Error]:
        """Remove a callback subscription."""
        with self._condition:
            if subscription_id in self._callbacks:
                del self._callbacks[subscription_id]
                return Result.ok(True)
        return Result.ok(False)

    @property
    def dropped_count(self) -> int:
        """Return the number of events evicted by the retention bound."""
        with self._condition:
            return self._dropped

    def metrics(self) -> Dict[str, int]:
        """Return bounded local retention and subscriber metrics."""
        with self._condition:
            return {
                "retained_events": len(self._events),
                "max_events": self._events.maxlen or 0,
                "dropped_events": self._dropped,
                "subscriber_count": len(self._callbacks),
                "published_events": self._published,
                "subscriber_failures": self._subscriber_failures,
                "exporter_failures": self._exporter_failures,
                "journal_failures": self._journal_failures,
                "publish_latency_total_ms": self._publish_latency_total_ms,
                "publish_latency_max_ms": self._publish_latency_max_ms,
                "publish_latency_avg_ms": (
                    self._publish_latency_total_ms // self._published
                    if self._published
                    else 0
                ),
                "publish_latency_sample_count": len(self._publish_latency_samples),
                "publish_latency_p50_ms": _percentile(
                    list(self._publish_latency_samples), 50
                ),
                "publish_latency_p95_ms": _percentile(
                    list(self._publish_latency_samples), 95
                ),
                "publish_latency_p99_ms": _percentile(
                    list(self._publish_latency_samples), 99
                ),
            }
