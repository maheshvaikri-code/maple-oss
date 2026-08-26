"""
Copyright (C) 2025 Mahesh Vaijainthymala Krishnamoorthy (Mahesh Vaikri)

This file is part of MAPLE - Multi Agent Protocol Language Engine.

MAPLE - Multi Agent Protocol Language Engine is free software: you can redistribute it and/or
modify it under the terms of the GNU Affero General Public License as published by the Free Software
Foundation, either version 3 of the License, or (at your option) any later version.
MAPLE - Multi Agent Protocol Language Engine is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A
PARTICULAR PURPOSE. See the GNU Affero General Public License for more details. You should have
received a copy of the GNU Affero General Public License along with MAPLE - Multi Agent Protocol
Language Engine. If not, see <https://www.gnu.org/licenses/>.
"""

# Observability for MAPLE autonomous agents.

from __future__ import annotations

import json
import math
import threading
import time
import uuid
from collections import deque
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any, Deque, Dict, List, Mapping, Optional, Tuple

from ..core.result import Result
from .events import RedactionPolicy

Error = Dict[str, Any]

_SPAN_TERMINAL_STATUSES: Tuple[str, ...] = ("ok", "error", "cancelled")
_MAX_SPAN_ID_LENGTH = 128
_MAX_SPAN_NAME_LENGTH = 128
_MAX_SPANS = 100_000
_MAX_SPAN_ATTRIBUTES = 32
_MAX_ATTRIBUTE_KEY_LENGTH = 128
_MAX_ATTRIBUTE_STRING_LENGTH = 1_024
_MAX_ATTRIBUTE_BYTES = 16_384


@dataclass
class DecisionTrace:
    """A single decision trace from the ReAct loop."""

    agent_id: str
    goal_id: str
    step_number: int
    timestamp: float
    prompt_summary: str
    response_summary: str
    tool_calls: List[Dict[str, Any]] = field(default_factory=list)
    tool_results: List[Dict[str, Any]] = field(default_factory=list)
    token_usage: Dict[str, int] = field(default_factory=dict)
    duration_ms: float = 0.0
    provider_request_id: Optional[str] = None
    trace_id: Optional[str] = None
    span_id: Optional[str] = None


def _span_error(error_type: str, message: str, **details: Any) -> Error:
    error: Error = {"errorType": error_type, "message": message}
    if details:
        error["details"] = details
    return error


def _valid_span_id(value: Any, *, allow_none: bool = False) -> bool:
    if value is None:
        return allow_none
    return (
        isinstance(value, str)
        and bool(value)
        and len(value) <= _MAX_SPAN_ID_LENGTH
        and not any(ord(char) < 32 for char in value)
    )


def _valid_span_time(value: Any) -> bool:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(float(value))
    )


@dataclass(frozen=True)
class TraceSpan:
    """An immutable, bounded local span record.

    Span attributes are deliberately flat JSON scalars. This makes the record
    safe to snapshot and prevents prompts or tool payloads from becoming an
    accidental tracing persistence boundary.
    """

    trace_id: str
    span_id: str
    name: str
    start_time: float
    end_time: Optional[float] = None
    parent_span_id: Optional[str] = None
    status: str = "running"
    attributes: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not _valid_span_id(self.trace_id) or not _valid_span_id(self.span_id):
            raise ValueError("trace_id and span_id must be bounded non-empty strings")
        if (
            not isinstance(self.name, str)
            or not self.name
            or len(self.name) > _MAX_SPAN_NAME_LENGTH
            or any(ord(char) < 32 for char in self.name)
        ):
            raise ValueError("span name must be bounded and free of control characters")
        if not _valid_span_time(self.start_time):
            raise ValueError("span start_time must be finite")
        if self.end_time is not None and (
            not _valid_span_time(self.end_time) or self.end_time < self.start_time
        ):
            raise ValueError("span end_time must be finite and after start_time")
        if self.parent_span_id is not None and not _valid_span_id(self.parent_span_id):
            raise ValueError("parent_span_id must be bounded when provided")
        if self.status not in ("running",) + _SPAN_TERMINAL_STATUSES:
            raise ValueError("span status is invalid")
        if (self.end_time is None) != (self.status == "running"):
            raise ValueError("running spans need no end_time; terminal spans need one")
        if not isinstance(self.attributes, Mapping):
            raise ValueError("span attributes must be a mapping")
        normalized: Dict[str, Any] = {}
        for key, value in self.attributes.items():
            if (
                not isinstance(key, str)
                or not key
                or len(key) > _MAX_ATTRIBUTE_KEY_LENGTH
                or any(ord(char) < 32 for char in key)
            ):
                raise ValueError("span attribute keys must be bounded strings")
            if not isinstance(value, (str, bool, int, float)) and value is not None:
                raise ValueError("span attributes must contain JSON scalar values")
            if isinstance(value, float) and not math.isfinite(value):
                raise ValueError("span attributes must contain finite numbers")
            if isinstance(value, str) and len(value) > _MAX_ATTRIBUTE_STRING_LENGTH:
                raise ValueError("span attribute strings are too long")
            normalized[key] = value
        if len(normalized) > _MAX_SPAN_ATTRIBUTES:
            raise ValueError("span attribute count exceeds the limit")
        try:
            attribute_bytes = len(
                json.dumps(
                    normalized,
                    ensure_ascii=False,
                    separators=(",", ":"),
                    allow_nan=False,
                ).encode("utf-8")
            )
        except (TypeError, ValueError, OverflowError) as exc:
            raise ValueError("span attributes must be JSON serializable") from exc
        if attribute_bytes > _MAX_ATTRIBUTE_BYTES:
            raise ValueError("span attributes exceed the byte limit")
        object.__setattr__(self, "attributes", MappingProxyType(normalized))

    def to_dict(self) -> Dict[str, Any]:
        """Return a JSON-compatible copy of the span record."""
        return {
            "trace_id": self.trace_id,
            "span_id": self.span_id,
            "name": self.name,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "parent_span_id": self.parent_span_id,
            "status": self.status,
            "attributes": dict(self.attributes),
        }


class SpanRecorder:
    """Thread-safe bounded recorder for local trace spans.

    The recorder retains the newest ``max_spans`` records. It does not export,
    persist, or schedule spans; those are host-owned concerns.
    """

    def __init__(
        self,
        *,
        max_spans: int = 1_000,
        redaction: Optional[RedactionPolicy] = None,
    ) -> None:
        if (
            not isinstance(max_spans, int)
            or isinstance(max_spans, bool)
            or max_spans <= 0
            or max_spans > _MAX_SPANS
        ):
            raise ValueError(f"max_spans must be an integer from 1 to {_MAX_SPANS}")
        self.max_spans = max_spans
        self.redaction = redaction or RedactionPolicy(
            max_depth=2,
            max_items=_MAX_SPAN_ATTRIBUTES,
            max_string_length=_MAX_ATTRIBUTE_STRING_LENGTH,
        )
        config_error = self.redaction.validate()
        if config_error is not None:
            raise ValueError(config_error["message"])
        self._spans: Deque[TraceSpan] = deque(maxlen=max_spans)
        self._by_id: Dict[str, TraceSpan] = {}
        self._dropped = 0
        self._lock = threading.RLock()

    def _prepare_attributes(
        self, attributes: Optional[Mapping[str, Any]]
    ) -> Result[Dict[str, Any], Error]:
        if attributes is None:
            return Result.ok({})
        if not isinstance(attributes, Mapping):
            return Result.err(
                _span_error(
                    "SPAN_ATTRIBUTES_INVALID", "span attributes must be a mapping."
                )
            )
        if len(attributes) > _MAX_SPAN_ATTRIBUTES:
            return Result.err(
                _span_error(
                    "SPAN_ATTRIBUTES_TOO_LARGE",
                    "span attributes exceed the item limit.",
                )
            )
        redacted = self.redaction.redact(dict(attributes))
        if redacted.is_err():
            return Result.err(
                _span_error(
                    "SPAN_ATTRIBUTES_INVALID",
                    "span attributes are invalid.",
                    cause=redacted.unwrap_err().get("errorType", "UNKNOWN"),
                )
            )
        value = redacted.unwrap()
        if not isinstance(value, Mapping):
            return Result.err(
                _span_error(
                    "SPAN_ATTRIBUTES_INVALID", "span attributes must be an object."
                )
            )
        output: Dict[str, Any] = {}
        for key, item in value.items():
            if (
                not isinstance(key, str)
                or not key
                or len(key) > _MAX_ATTRIBUTE_KEY_LENGTH
                or any(ord(char) < 32 for char in key)
            ):
                return Result.err(
                    _span_error(
                        "SPAN_ATTRIBUTES_INVALID", "span attribute keys are invalid."
                    )
                )
            if not isinstance(item, (str, bool, int, float)) and item is not None:
                return Result.err(
                    _span_error(
                        "SPAN_ATTRIBUTES_INVALID",
                        "span attributes must contain scalar values.",
                    )
                )
            if isinstance(item, float) and not math.isfinite(item):
                return Result.err(
                    _span_error(
                        "SPAN_ATTRIBUTES_INVALID",
                        "span attributes need finite numbers.",
                    )
                )
            if isinstance(item, str) and len(item) > _MAX_ATTRIBUTE_STRING_LENGTH:
                return Result.err(
                    _span_error(
                        "SPAN_ATTRIBUTES_TOO_LARGE",
                        "span attribute strings are too long.",
                    )
                )
            output[key] = item
        try:
            size = len(
                json.dumps(
                    output,
                    ensure_ascii=False,
                    separators=(",", ":"),
                    allow_nan=False,
                ).encode("utf-8")
            )
        except (TypeError, ValueError, OverflowError):
            return Result.err(
                _span_error(
                    "SPAN_ATTRIBUTES_INVALID",
                    "span attributes must be JSON serializable.",
                )
            )
        if size > _MAX_ATTRIBUTE_BYTES:
            return Result.err(
                _span_error(
                    "SPAN_ATTRIBUTES_TOO_LARGE",
                    "span attributes exceed the byte limit.",
                )
            )
        return Result.ok(output)

    def start_span(
        self,
        name: str,
        *,
        trace_id: Optional[str] = None,
        parent_span_id: Optional[str] = None,
        attributes: Optional[Mapping[str, Any]] = None,
        start_time: Optional[float] = None,
    ) -> Result[TraceSpan, Error]:
        """Start and retain a bounded span, optionally under an open parent."""
        if (
            not isinstance(name, str)
            or not name
            or len(name) > _MAX_SPAN_NAME_LENGTH
            or any(ord(char) < 32 for char in name)
        ):
            return Result.err(
                _span_error("SPAN_INPUT_INVALID", "span name is invalid.")
            )
        if trace_id is not None and not _valid_span_id(trace_id):
            return Result.err(_span_error("SPAN_INPUT_INVALID", "trace_id is invalid."))
        if parent_span_id is not None and not _valid_span_id(parent_span_id):
            return Result.err(
                _span_error("SPAN_INPUT_INVALID", "parent_span_id is invalid.")
            )
        effective_start = time.time() if start_time is None else start_time
        if not _valid_span_time(effective_start):
            return Result.err(
                _span_error("SPAN_INPUT_INVALID", "start_time must be finite.")
            )
        prepared = self._prepare_attributes(attributes)
        if prepared.is_err():
            return Result.err(prepared.unwrap_err())

        with self._lock:
            parent = self._by_id.get(parent_span_id) if parent_span_id else None
            if parent_span_id is not None and parent is None:
                return Result.err(
                    _span_error("SPAN_PARENT_NOT_FOUND", "parent span is not retained.")
                )
            if parent is not None:
                if parent.end_time is not None:
                    return Result.err(
                        _span_error(
                            "SPAN_PARENT_CLOSED", "parent span is already finished."
                        )
                    )
                if trace_id is not None and trace_id != parent.trace_id:
                    return Result.err(
                        _span_error(
                            "SPAN_TRACE_MISMATCH", "child and parent trace IDs differ."
                        )
                    )
                effective_trace_id = parent.trace_id
            else:
                effective_trace_id = trace_id or uuid.uuid4().hex
            span = TraceSpan(
                trace_id=effective_trace_id,
                span_id=uuid.uuid4().hex,
                name=name,
                start_time=float(effective_start),
                parent_span_id=parent_span_id,
                attributes=prepared.unwrap(),
            )
            if len(self._spans) == self.max_spans:
                evicted = self._spans[0]
                self._by_id.pop(evicted.span_id, None)
                self._dropped += 1
            self._spans.append(span)
            self._by_id[span.span_id] = span
            return Result.ok(span)

    def finish_span(
        self,
        span_id: str,
        *,
        status: str = "ok",
        attributes: Optional[Mapping[str, Any]] = None,
        end_time: Optional[float] = None,
    ) -> Result[TraceSpan, Error]:
        """Finish one retained open span exactly once."""
        if not _valid_span_id(span_id):
            return Result.err(_span_error("SPAN_INPUT_INVALID", "span_id is invalid."))
        if status not in _SPAN_TERMINAL_STATUSES:
            return Result.err(
                _span_error(
                    "SPAN_INPUT_INVALID", "status must be a terminal span status."
                )
            )
        effective_end = time.time() if end_time is None else end_time
        if not _valid_span_time(effective_end):
            return Result.err(
                _span_error("SPAN_INPUT_INVALID", "end_time must be finite.")
            )
        prepared = self._prepare_attributes(attributes)
        if prepared.is_err():
            return Result.err(prepared.unwrap_err())
        with self._lock:
            span = self._by_id.get(span_id)
            if span is None:
                return Result.err(
                    _span_error("SPAN_NOT_FOUND", "span is not retained.")
                )
            if span.end_time is not None:
                return Result.err(
                    _span_error("SPAN_ALREADY_FINISHED", "span is already finished.")
                )
            if effective_end < span.start_time:
                return Result.err(
                    _span_error(
                        "SPAN_INPUT_INVALID", "end_time must not precede start_time."
                    )
                )
            merged = dict(span.attributes)
            merged.update(prepared.unwrap())
            try:
                finished = TraceSpan(
                    trace_id=span.trace_id,
                    span_id=span.span_id,
                    name=span.name,
                    start_time=span.start_time,
                    end_time=float(effective_end),
                    parent_span_id=span.parent_span_id,
                    status=status,
                    attributes=merged,
                )
            except ValueError as exc:
                return Result.err(
                    _span_error(
                        "SPAN_ATTRIBUTES_TOO_LARGE",
                        "finished span exceeds the attribute limit.",
                        reason=str(exc),
                    )
                )
            for index, candidate in enumerate(self._spans):
                if candidate.span_id == span_id:
                    self._spans[index] = finished
                    break
            else:
                return Result.err(
                    _span_error("SPAN_NOT_FOUND", "span is not retained.")
                )
            self._by_id[span_id] = finished
            return Result.ok(finished)

    def get_span(self, span_id: str) -> Result[TraceSpan, Error]:
        """Return one retained span."""
        if not _valid_span_id(span_id):
            return Result.err(_span_error("SPAN_INPUT_INVALID", "span_id is invalid."))
        with self._lock:
            span = self._by_id.get(span_id)
        if span is None:
            return Result.err(_span_error("SPAN_NOT_FOUND", "span is not retained."))
        return Result.ok(span)

    def snapshot(
        self, *, trace_id: Optional[str] = None
    ) -> Result[List[TraceSpan], Error]:
        """Return retained spans in creation order, optionally by trace."""
        if trace_id is not None and not _valid_span_id(trace_id):
            return Result.err(_span_error("SPAN_INPUT_INVALID", "trace_id is invalid."))
        with self._lock:
            spans = list(self._spans)
        if trace_id is not None:
            spans = [span for span in spans if span.trace_id == trace_id]
        return Result.ok(spans)

    def export_json(self, *, trace_id: Optional[str] = None) -> Result[str, Error]:
        """Return retained spans as bounded JSON without exporting remotely."""
        spans = self.snapshot(trace_id=trace_id)
        if spans.is_err():
            return Result.err(spans.unwrap_err())
        try:
            return Result.ok(
                json.dumps(
                    [span.to_dict() for span in spans.unwrap()],
                    ensure_ascii=False,
                    separators=(",", ":"),
                    allow_nan=False,
                )
            )
        except (TypeError, ValueError, OverflowError):
            return Result.err(
                _span_error(
                    "SPAN_EXPORT_INVALID", "retained spans are not JSON serializable."
                )
            )

    @property
    def span_count(self) -> int:
        """Return the number of retained spans."""
        with self._lock:
            return len(self._spans)

    def metrics(self) -> Dict[str, int]:
        """Return bounded local retention and open-span metrics."""
        with self._lock:
            return {
                "retained_spans": len(self._spans),
                "max_spans": self.max_spans,
                "dropped_spans": self._dropped,
                "open_spans": sum(span.status == "running" for span in self._spans),
            }


class DecisionLogger:
    """Logs and retrieves decision traces for debugging and observability."""

    def __init__(self, max_traces: int = 1000):
        self._traces: deque = deque(maxlen=max_traces)
        self._by_goal: Dict[str, List[DecisionTrace]] = {}

    def log_decision(self, trace: DecisionTrace) -> None:
        """Log a decision trace."""
        self._traces.append(trace)
        if trace.goal_id not in self._by_goal:
            self._by_goal[trace.goal_id] = []
        self._by_goal[trace.goal_id].append(trace)

    def get_traces(self, goal_id: Optional[str] = None) -> List[DecisionTrace]:
        """Retrieve decision traces, optionally filtered by goal."""
        if goal_id:
            return list(self._by_goal.get(goal_id, []))
        return list(self._traces)

    def get_summary(self, goal_id: str) -> Dict[str, Any]:
        """Get a summary of decisions for a goal."""
        traces = self._by_goal.get(goal_id, [])
        if not traces:
            return {"goal_id": goal_id, "steps": 0}

        total_tokens = sum(t.token_usage.get("total_tokens", 0) for t in traces)
        total_duration = sum(t.duration_ms for t in traces)
        tool_call_count = sum(len(t.tool_calls) for t in traces)

        return {
            "goal_id": goal_id,
            "steps": len(traces),
            "total_tokens": total_tokens,
            "total_duration_ms": total_duration,
            "tool_calls": tool_call_count,
            "first_step": traces[0].timestamp if traces else None,
            "last_step": traces[-1].timestamp if traces else None,
        }

    def export_json(self, goal_id: Optional[str] = None) -> str:
        """Export traces as JSON."""
        traces = self.get_traces(goal_id)
        return json.dumps(
            [
                {
                    "agent_id": t.agent_id,
                    "goal_id": t.goal_id,
                    "step_number": t.step_number,
                    "timestamp": t.timestamp,
                    "prompt_summary": t.prompt_summary,
                    "response_summary": t.response_summary,
                    "tool_calls": t.tool_calls,
                    "tool_results": t.tool_results,
                    "token_usage": t.token_usage,
                    "duration_ms": t.duration_ms,
                    "provider_request_id": t.provider_request_id,
                    "trace_id": t.trace_id,
                    "span_id": t.span_id,
                }
                for t in traces
            ],
            indent=2,
        )

    @property
    def trace_count(self) -> int:
        return len(self._traces)


class AgentSnapshot:
    """Captures a point-in-time snapshot of an autonomous agent's state."""

    @staticmethod
    def capture(agent: Any) -> Dict[str, Any]:
        """Capture a snapshot of an autonomous agent."""
        snapshot = {
            "agent_id": agent.agent_id,
            "timestamp": time.time(),
            "status": getattr(agent, "status", "unknown"),
        }

        # LLM usage stats
        if hasattr(agent, "llm"):
            snapshot["llm_usage"] = agent.llm.get_usage_stats()

        # Working memory
        if hasattr(agent, "memory"):
            snapshot["working_memory"] = {
                "entries": agent.memory.working.size,
                "token_usage": agent.memory.working.token_usage,
                "max_tokens": agent.memory.working.max_tokens,
            }

        # Active goals
        if hasattr(agent, "_active_goals"):
            snapshot["active_goals"] = {
                gid: {
                    "description": g.description,
                    "status": g.status,
                    "steps": len(g.reasoning_trace),
                }
                for gid, g in agent._active_goals.items()
            }

        # Agent metrics
        for attr in ["messages_sent", "messages_received", "messages_failed"]:
            if hasattr(agent, attr):
                snapshot[attr] = getattr(agent, attr)

        # Tool registry
        if hasattr(agent, "tool_registry"):
            snapshot["registered_tools"] = [
                t.name for t in agent.tool_registry.list_tools()
            ]

        return snapshot
