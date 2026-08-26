"""Bounded event streaming and redaction primitives for MAPLE."""

from __future__ import annotations

import json
import threading
import time
from collections import deque
from dataclasses import dataclass
from typing import Any, Callable, Deque, Dict, List, Mapping, Optional, Protocol, Tuple

from ..core.result import Result

Error = Dict[str, Any]
EventCallback = Callable[["AgentEvent"], None]


class CancellationSignal(Protocol):
    """Minimal cooperative cancellation contract for event waiters."""

    def is_cancelled(self) -> bool:
        """Return whether cancellation has been requested."""


class EventExporter(Protocol):
    """Host-owned sink for already-redacted agent events."""

    def export(self, event: "AgentEvent") -> None:
        """Receive one bounded event without changing the run outcome."""


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


class EventStream:
    """Thread-safe bounded event stream with redacted callbacks."""

    def __init__(
        self,
        *,
        max_events: int = 1_000,
        max_payload_bytes: int = 1_048_576,
        max_subscribers: int = 1_000,
        redaction: Optional[RedactionPolicy] = None,
        exporter: Optional[EventExporter] = None,
    ) -> None:
        self.max_events = max_events
        self.max_payload_bytes = max_payload_bytes
        self.max_subscribers = max_subscribers
        self.redaction = redaction or RedactionPolicy()
        self.exporter = exporter
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
        self._condition = threading.Condition(threading.RLock())

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
        return self.redaction.validate()

    def publish(
        self,
        event_type: str,
        payload: Any,
        *,
        run_id: Optional[str] = None,
    ) -> Result[AgentEvent, Error]:
        """Redact, bound, retain, and deliver one event."""
        config_error = self._validate_config()
        if config_error is not None:
            return Result.err(config_error)
        if not isinstance(event_type, str) or not event_type or len(event_type) > 128:
            return Result.err(
                _error(
                    "EVENT_INPUT_INVALID", "event_type must be bounded and non-empty."
                )
            )
        if any(ord(char) < 32 for char in event_type):
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
        if run_id is not None and any(ord(char) < 32 for char in run_id):
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
        with self._condition:
            if len(self._events) == self.max_events:
                self._dropped += 1
            event = AgentEvent(
                sequence=self._next_sequence,
                event_type=event_type,
                timestamp=time.time(),
                payload=redacted.unwrap(),
                run_id=run_id,
            )
            self._next_sequence += 1
            self._events.append(event)
            callbacks = list(self._callbacks.values())
            self._condition.notify_all()
        for callback in callbacks:
            try:
                callback(event)
            except Exception:
                continue
        if self.exporter is not None:
            try:
                self.exporter.export(event)
            except Exception:
                # Export is an observability side effect and must not fail a run.
                pass
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
                "max_events": self.max_events,
                "dropped_events": self._dropped,
                "subscriber_count": len(self._callbacks),
            }
