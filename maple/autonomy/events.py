"""Bounded event streaming and redaction primitives for MAPLE."""

from __future__ import annotations

import json
import threading
import time
from collections import deque
from dataclasses import dataclass
from typing import Any, Callable, Deque, Dict, List, Mapping, Optional, Tuple

from ..core.result import Result

Error = Dict[str, Any]
EventCallback = Callable[["AgentEvent"], None]


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
                output = []
                for item in current:
                    item_result = visit(item, depth + 1)
                    if item_result.is_err():
                        return item_result
                    output.append(item_result.unwrap())
                return Result.ok(output)
            if isinstance(current, Mapping):
                if len(current) > self.max_items:
                    return Result.err(
                        _error(
                            "EVENT_PAYLOAD_TOO_LARGE",
                            "event object exceeds the item limit.",
                        )
                    )
                output: Dict[str, Any] = {}
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
                        output[key] = self.replacement
                        continue
                    item_result = visit(item, depth + 1)
                    if item_result.is_err():
                        return item_result
                    output[key] = item_result.unwrap()
                return Result.ok(output)
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


class EventStream:
    """Thread-safe bounded event stream with redacted callbacks."""

    def __init__(
        self,
        *,
        max_events: int = 1_000,
        max_payload_bytes: int = 1_048_576,
        max_subscribers: int = 1_000,
        redaction: Optional[RedactionPolicy] = None,
    ) -> None:
        self.max_events = max_events
        self.max_payload_bytes = max_payload_bytes
        self.max_subscribers = max_subscribers
        self.redaction = redaction or RedactionPolicy()
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

    def wait_for(
        self, after_sequence: int, timeout: Optional[float] = None
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
        deadline = None if timeout is None else time.monotonic() + timeout
        with self._condition:
            while not any(event.sequence > after_sequence for event in self._events):
                remaining = None if deadline is None else deadline - time.monotonic()
                if remaining is not None and remaining <= 0:
                    return Result.err(
                        _error("EVENT_WAIT_TIMEOUT", "no event arrived before timeout.")
                    )
                self._condition.wait(remaining)
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
