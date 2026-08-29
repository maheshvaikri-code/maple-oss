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
"""Bounded conversation sessions for local agent hosts."""

from __future__ import annotations

import json
import math
import os
import re
import tempfile
import threading
import time
import uuid
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Protocol, Tuple, Union

from ..core.result import Result
from ..llm.types import (
    ChatContent,
    ChatMessage,
    ChatRole,
    ImageContent,
    ToolCall,
    validate_chat_content,
)

Error = Dict[str, Any]
_IDENTIFIER = re.compile(r"^[A-Za-z0-9_.:-]{1,128}$")
_ROLES = {role.value for role in ChatRole}
_MAX_JSON_DEPTH = 16
_MAX_JSON_ITEMS = 1_000

DEFAULT_MAX_SESSIONS = 1_000
DEFAULT_MAX_MESSAGES = 100
DEFAULT_MAX_MESSAGE_BYTES = 128 * 1024
DEFAULT_MAX_METADATA_BYTES = 64 * 1024
DEFAULT_MAX_SESSION_BYTES = 1 * 1024 * 1024
DEFAULT_MAX_HISTORY = 100
MAX_HISTORY = 10_000


def _error(error_type: str, message: str, **details: Any) -> Error:
    result: Error = {"errorType": error_type, "message": message}
    if details:
        result["details"] = details
    return result


def _valid_identifier(value: Any, field_name: str) -> Optional[Error]:
    if not isinstance(value, str) or not _IDENTIFIER.fullmatch(value):
        return _error(
            "INVALID_IDENTIFIER",
            f"{field_name} must contain 1-128 letters, numbers, '_', '.', ':', or '-'.",
            field=field_name,
        )
    return None


def _valid_text(
    value: Any, field_name: str, *, allow_empty: bool = False
) -> Optional[Error]:
    if not isinstance(value, str) or (not allow_empty and not value):
        return _error(
            "SESSION_TEXT_INVALID",
            f"{field_name} must be a string"
            + ("" if allow_empty else " and must not be empty"),
            field=field_name,
        )
    return None


def _validate_json_value(
    value: Any,
    *,
    path: str = "$",
    depth: int = 0,
) -> Optional[Error]:
    if depth > _MAX_JSON_DEPTH:
        return _error(
            "SESSION_METADATA_DEPTH",
            "Session metadata is nested too deeply.",
            path=path,
        )
    if value is None or isinstance(value, (bool, int, str)):
        return None
    if isinstance(value, float):
        if math.isfinite(value):
            return None
        return _error(
            "SESSION_METADATA_VALUE",
            "Session metadata contains a non-finite number.",
            path=path,
        )
    if isinstance(value, list):
        if len(value) > _MAX_JSON_ITEMS:
            return _error(
                "SESSION_METADATA_SIZE",
                "Session metadata contains too many list items.",
                path=path,
            )
        for index, item in enumerate(value):
            error = _validate_json_value(item, path=f"{path}[{index}]", depth=depth + 1)
            if error:
                return error
        return None
    if isinstance(value, dict):
        if len(value) > _MAX_JSON_ITEMS:
            return _error(
                "SESSION_METADATA_SIZE",
                "Session metadata contains too many object keys.",
                path=path,
            )
        for key, item in value.items():
            if not isinstance(key, str):
                return _error(
                    "SESSION_METADATA_KEY",
                    "Session metadata keys must be strings.",
                    path=path,
                )
            error = _validate_json_value(item, path=f"{path}.{key}", depth=depth + 1)
            if error:
                return error
        return None
    return _error(
        "SESSION_METADATA_VALUE",
        "Session metadata must be JSON-compatible.",
        path=path,
    )


def _copy_json(value: Any, *, field_name: str, max_bytes: int) -> Result[Any, Error]:
    error = _validate_json_value(value, path=field_name)
    if error:
        return Result.err(error)
    try:
        encoded = json.dumps(
            value,
            ensure_ascii=False,
            allow_nan=False,
            separators=(",", ":"),
        )
        if len(encoded.encode("utf-8")) > max_bytes:
            return Result.err(
                _error(
                    "SESSION_METADATA_SIZE",
                    f"{field_name} exceeds the configured byte limit.",
                    max_bytes=max_bytes,
                )
            )
        return Result.ok(json.loads(encoded))
    except (TypeError, ValueError, json.JSONDecodeError) as exc:
        return Result.err(
            _error(
                "SESSION_METADATA_VALUE",
                f"{field_name} is not JSON serializable.",
                reason=str(exc)[:256],
            )
        )


def _content_to_json(
    content: ChatContent,
) -> Union[str, List[Union[str, Dict[str, Any]]]]:
    """Convert typed chat content into a JSON-safe session representation."""

    validate_chat_content(content)
    if isinstance(content, str):
        return content
    encoded: List[Union[str, Dict[str, Any]]] = []
    for part in content:
        if isinstance(part, str):
            encoded.append(part)
        else:
            encoded.append(
                {
                    "type": "image",
                    "source": part.source,
                    "mime_type": part.mime_type,
                    "detail": part.detail,
                }
            )
    return encoded


def _content_from_json(value: Any) -> ChatContent:
    """Restore text or typed image parts from a persisted session message."""

    if isinstance(value, str):
        return value
    if not isinstance(value, list) or not value or len(value) > 64:
        raise ValueError("session message content must be text or 1-64 parts")
    parts: List[Union[str, ImageContent]] = []
    for item in value:
        if isinstance(item, str):
            parts.append(item)
            continue
        if not isinstance(item, Mapping) or item.get("type") != "image":
            raise ValueError("session content parts must be text or image objects")
        try:
            source = item.get("source")
            if not isinstance(source, str):
                raise ValueError("image source must be a string")
            mime_type = item.get("mime_type")
            if mime_type is not None and not isinstance(mime_type, str):
                raise ValueError("image mime_type must be a string")
            detail = item.get("detail", "auto")
            if not isinstance(detail, str):
                raise ValueError("image detail must be a string")
            parts.append(
                ImageContent(
                    source=source,
                    mime_type=mime_type,
                    detail=detail,
                )
            )
        except (TypeError, ValueError) as exc:
            raise ValueError("invalid session image content") from exc
    content: ChatContent = parts
    validate_chat_content(content)
    return content


@dataclass(frozen=True)
class SessionMessage:
    """One JSON-safe conversation message stored as data."""

    role: str
    content: ChatContent
    message_id: str = field(default_factory=lambda: f"msg-{uuid.uuid4().hex}")
    name: Optional[str] = None
    tool_call_id: Optional[str] = None
    tool_calls: Tuple[Dict[str, Any], ...] = ()
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        """Return a JSON-safe persistence representation."""
        return {
            "message_id": self.message_id,
            "role": self.role,
            "content": _content_to_json(self.content),
            "name": self.name,
            "tool_call_id": self.tool_call_id,
            "tool_calls": [dict(call) for call in self.tool_calls],
            "metadata": dict(self.metadata),
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "SessionMessage":
        """Parse one message without executing any embedded value."""
        if not isinstance(data, Mapping):
            raise ValueError("session message must be an object")
        for field_name in ("role", "content"):
            if field_name not in data:
                raise ValueError("session message is missing a required field")
        if data["role"] not in _ROLES:
            raise ValueError("invalid session message role")
        try:
            content = _content_from_json(data["content"])
        except (TypeError, ValueError) as exc:
            raise ValueError("invalid session message content") from exc
        message_id = data.get("message_id", f"msg-{uuid.uuid4().hex}")
        if _valid_identifier(message_id, "message_id"):
            raise ValueError("invalid session message ID")
        name = data.get("name")
        if name is not None and _valid_text(name, "name"):
            raise ValueError("invalid session message name")
        tool_call_id = data.get("tool_call_id")
        if tool_call_id is not None and _valid_text(tool_call_id, "tool_call_id"):
            raise ValueError("invalid session tool call ID")
        raw_calls = data.get("tool_calls", [])
        if not isinstance(raw_calls, (list, tuple)) or len(raw_calls) > _MAX_JSON_ITEMS:
            raise ValueError("invalid session tool calls")
        tool_calls: List[Dict[str, Any]] = []
        for call in raw_calls:
            if not isinstance(call, Mapping):
                raise ValueError("session tool calls must be objects")
            if _valid_identifier(call.get("id"), "tool_call.id"):
                raise ValueError("invalid session tool call ID")
            if _valid_text(call.get("name"), "tool_call.name"):
                raise ValueError("invalid session tool call name")
            arguments = call.get("arguments")
            if not isinstance(arguments, Mapping):
                raise ValueError("session tool call arguments must be an object")
            arguments_copy = _copy_json(
                dict(arguments),
                field_name="tool_call.arguments",
                max_bytes=DEFAULT_MAX_MESSAGE_BYTES,
            )
            if arguments_copy.is_err():
                raise ValueError(arguments_copy.unwrap_err()["message"])
            tool_calls.append(
                {
                    "id": call["id"],
                    "name": call["name"],
                    "arguments": arguments_copy.unwrap(),
                }
            )
        metadata = data.get("metadata", {})
        if not isinstance(metadata, Mapping):
            raise ValueError("session metadata must be an object")
        metadata_copy = _copy_json(
            dict(metadata),
            field_name="metadata",
            max_bytes=DEFAULT_MAX_METADATA_BYTES,
        )
        if metadata_copy.is_err():
            raise ValueError(metadata_copy.unwrap_err()["message"])
        created_at = float(data.get("created_at", time.time()))
        if not math.isfinite(created_at):
            raise ValueError("session message timestamp must be finite")
        return cls(
            role=data["role"],
            content=content,
            message_id=message_id,
            name=name,
            tool_call_id=tool_call_id,
            tool_calls=tuple(tool_calls),
            metadata=metadata_copy.unwrap(),
            created_at=created_at,
        )

    @classmethod
    def from_chat_message(
        cls, message: ChatMessage, *, metadata: Optional[Mapping[str, Any]] = None
    ) -> "SessionMessage":
        """Convert an existing MAPLE LLM message into stored session data."""
        calls = tuple(
            {
                "id": call.id,
                "name": call.name,
                "arguments": dict(call.arguments),
            }
            for call in (message.tool_calls or [])
        )
        return cls(
            role=message.role.value,
            content=message.content,
            name=message.name,
            tool_call_id=message.tool_call_id,
            tool_calls=calls,
            metadata=dict(metadata or {}),
        )

    def to_chat_message(self) -> ChatMessage:
        """Convert stored data back to the typed LLM message boundary."""
        calls = [
            ToolCall(
                id=call["id"], name=call["name"], arguments=dict(call["arguments"])
            )
            for call in self.tool_calls
        ]
        return ChatMessage(
            role=ChatRole(self.role),
            content=self.content,
            name=self.name,
            tool_call_id=self.tool_call_id,
            tool_calls=calls or None,
        )


@dataclass(frozen=True)
class SessionSnapshot:
    """A versioned, bounded view of one conversation session."""

    session_id: str
    messages: Tuple[SessionMessage, ...] = ()
    metadata: Dict[str, Any] = field(default_factory=dict)
    version: int = 0
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "session_id": self.session_id,
            "messages": [message.to_dict() for message in self.messages],
            "metadata": dict(self.metadata),
            "version": self.version,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "SessionSnapshot":
        if not isinstance(data, Mapping):
            raise ValueError("session snapshot must be an object")
        required = (
            "session_id",
            "messages",
            "metadata",
            "version",
            "created_at",
            "updated_at",
        )
        if any(field_name not in data for field_name in required):
            raise ValueError("session snapshot is missing a required field")
        if _valid_identifier(data.get("session_id"), "session_id"):
            raise ValueError("invalid session ID")
        raw_messages = data.get("messages", [])
        if not isinstance(raw_messages, list):
            raise ValueError("session messages must be a list")
        messages = tuple(SessionMessage.from_dict(item) for item in raw_messages)
        metadata = data.get("metadata", {})
        if not isinstance(metadata, Mapping):
            raise ValueError("session metadata must be an object")
        metadata_copy = _copy_json(
            dict(metadata),
            field_name="metadata",
            max_bytes=DEFAULT_MAX_METADATA_BYTES,
        )
        if metadata_copy.is_err():
            raise ValueError(metadata_copy.unwrap_err()["message"])
        version = data.get("version", 0)
        if not isinstance(version, int) or isinstance(version, bool) or version < 0:
            raise ValueError("invalid session version")
        created_at = float(data.get("created_at", time.time()))
        updated_at = float(data.get("updated_at", time.time()))
        if not math.isfinite(created_at) or not math.isfinite(updated_at):
            raise ValueError("session timestamps must be finite")
        return cls(
            session_id=data["session_id"],
            messages=messages,
            metadata=metadata_copy.unwrap(),
            version=version,
            created_at=created_at,
            updated_at=updated_at,
        )


@dataclass(frozen=True)
class _StoredSession:
    """Validated current snapshot and retained history for a file record."""

    snapshot: SessionSnapshot
    history: Tuple[SessionSnapshot, ...]


class SessionStore(Protocol):
    """Persistence contract for bounded conversation sessions."""

    def create(
        self,
        session_id: Optional[str] = None,
        *,
        metadata: Optional[Mapping[str, Any]] = None,
    ) -> Result[SessionSnapshot, Error]: ...

    def load(self, session_id: str) -> Result[Optional[SessionSnapshot], Error]: ...

    def append(
        self,
        session_id: str,
        message: SessionMessage,
        *,
        expected_version: Optional[int] = None,
    ) -> Result[SessionSnapshot, Error]: ...

    def clear(
        self,
        session_id: str,
        *,
        expected_version: Optional[int] = None,
    ) -> Result[SessionSnapshot, Error]: ...

    def history(
        self, session_id: str, *, limit: Optional[int] = None
    ) -> Result[Tuple[SessionSnapshot, ...], Error]: ...

    def fork(
        self,
        session_id: str,
        new_session_id: Optional[str] = None,
        *,
        at_version: Optional[int] = None,
        expected_version: Optional[int] = None,
    ) -> Result[SessionSnapshot, Error]: ...


class SessionCompactionStore(Protocol):
    """Optional host-supplied-summary compaction contract."""

    def compact(
        self,
        session_id: str,
        summary: str,
        *,
        keep_last: int = 8,
        expected_version: Optional[int] = None,
    ) -> Result[SessionSnapshot, Error]: ...


class _SessionStoreSupport:
    def _configure_limits(
        self,
        *,
        max_sessions: int,
        max_messages: int,
        max_message_bytes: int,
        max_metadata_bytes: int,
        max_session_bytes: int,
        max_history: int,
    ) -> None:
        limits = (
            max_sessions,
            max_messages,
            max_message_bytes,
            max_metadata_bytes,
            max_session_bytes,
            max_history,
        )
        if any(
            not isinstance(value, int) or isinstance(value, bool) or value <= 0
            for value in limits[:-1]
        ):
            raise ValueError("session limits must be positive integers")
        if (
            not isinstance(max_history, int)
            or isinstance(max_history, bool)
            or max_history <= 0
        ):
            raise ValueError("max_history must be a positive integer")
        if max_message_bytes > max_session_bytes:
            raise ValueError("max_message_bytes cannot exceed max_session_bytes")
        if max_history > MAX_HISTORY:
            raise ValueError(f"max_history cannot exceed {MAX_HISTORY}")
        self.max_sessions = max_sessions
        self.max_messages = max_messages
        self.max_message_bytes = max_message_bytes
        self.max_metadata_bytes = max_metadata_bytes
        self.max_session_bytes = max_session_bytes
        self.max_history = max_history

    def _session_id(self, session_id: Any) -> Result[str, Error]:
        error = _valid_identifier(session_id, "session_id")
        if error:
            return Result.err(error)
        return Result.ok(session_id)

    def _metadata(
        self, metadata: Optional[Mapping[str, Any]]
    ) -> Result[Dict[str, Any], Error]:
        if metadata is None:
            return Result.ok({})
        if not isinstance(metadata, Mapping):
            return Result.err(
                _error("SESSION_METADATA_VALUE", "Session metadata must be an object.")
            )
        copied = _copy_json(
            dict(metadata),
            field_name="metadata",
            max_bytes=self.max_metadata_bytes,
        )
        if copied.is_err():
            return Result.err(copied.unwrap_err())
        return Result.ok(copied.unwrap())

    def _history_limit(self, limit: Any) -> Result[int, Error]:
        if (
            not isinstance(limit, int)
            or isinstance(limit, bool)
            or limit <= 0
            or limit > self.max_history
        ):
            return Result.err(
                _error(
                    "SESSION_HISTORY_LIMIT",
                    (
                        "history limit must be a positive integer within the "
                        "configured bound."
                    ),
                    max_history=self.max_history,
                )
            )
        return Result.ok(limit)

    def _version(self, value: Any, field_name: str) -> Result[Optional[int], Error]:
        if value is not None and (
            not isinstance(value, int) or isinstance(value, bool) or value < 0
        ):
            return Result.err(
                _error(
                    "SESSION_VERSION_INVALID",
                    f"{field_name} must be a non-negative integer or null.",
                    field=field_name,
                )
            )
        return Result.ok(value)

    def _copy_snapshot(
        self, snapshot: SessionSnapshot
    ) -> Result[SessionSnapshot, Error]:
        try:
            encoded = json.dumps(
                snapshot.to_dict(),
                ensure_ascii=False,
                allow_nan=False,
                separators=(",", ":"),
            )
            if len(encoded.encode("utf-8")) > self.max_session_bytes:
                return Result.err(
                    _error(
                        "SESSION_SIZE_EXCEEDED",
                        "Session exceeds the configured byte limit.",
                        max_bytes=self.max_session_bytes,
                    )
                )
            copied = SessionSnapshot.from_dict(json.loads(encoded))
        except (TypeError, ValueError, json.JSONDecodeError) as exc:
            return Result.err(
                _error(
                    "SESSION_VALUE_INVALID",
                    "Session is not JSON serializable.",
                    reason=str(exc)[:256],
                )
            )
        if len(copied.messages) > self.max_messages:
            return Result.err(
                _error(
                    "SESSION_MESSAGE_LIMIT",
                    "Session contains more messages than allowed.",
                    max_messages=self.max_messages,
                )
            )
        seen_ids = set()
        for message in copied.messages:
            if message.message_id in seen_ids:
                return Result.err(
                    _error(
                        "SESSION_MESSAGE_DUPLICATE",
                        "Session contains duplicate message IDs.",
                        message_id=message.message_id,
                    )
                )
            seen_ids.add(message.message_id)
            message_size = len(
                json.dumps(message.to_dict(), ensure_ascii=False).encode("utf-8")
            )
            if message_size > self.max_message_bytes:
                return Result.err(
                    _error(
                        "SESSION_MESSAGE_SIZE",
                        "Session message exceeds the configured byte limit.",
                        max_bytes=self.max_message_bytes,
                    )
                )
        metadata_size = len(
            json.dumps(copied.metadata, ensure_ascii=False, allow_nan=False).encode(
                "utf-8"
            )
        )
        if metadata_size > self.max_metadata_bytes:
            return Result.err(
                _error(
                    "SESSION_METADATA_SIZE",
                    "Session metadata exceeds the configured byte limit.",
                    max_bytes=self.max_metadata_bytes,
                )
            )
        return Result.ok(copied)

    def _validate_history(
        self,
        history: Tuple[SessionSnapshot, ...],
        current: SessionSnapshot,
        *,
        max_history: Optional[int] = None,
    ) -> Result[Tuple[SessionSnapshot, ...], Error]:
        history_bound = self.max_history if max_history is None else max_history
        if not history or len(history) > history_bound:
            return Result.err(
                _error(
                    "SESSION_HISTORY_INVALID",
                    "Session history must contain 1-{} snapshots.".format(
                        history_bound
                    ),
                    max_history=self.max_history,
                )
            )
        copied_history: List[SessionSnapshot] = []
        previous_version = -1
        for snapshot in history:
            copied = self._copy_snapshot(snapshot)
            if copied.is_err():
                return Result.err(copied.unwrap_err())
            value = copied.unwrap()
            if (
                value.session_id != current.session_id
                or value.version <= previous_version
            ):
                return Result.err(
                    _error(
                        "SESSION_HISTORY_INVALID",
                        (
                            "Session history must use one session ID and strictly "
                            "increase versions."
                        ),
                    )
                )
            copied_history.append(value)
            previous_version = value.version
        if copied_history[-1].to_dict() != current.to_dict():
            return Result.err(
                _error(
                    "SESSION_HISTORY_INVALID",
                    "The newest history entry must equal the current snapshot.",
                )
            )
        try:
            history_bytes = len(
                json.dumps(
                    {
                        "schema_version": 2,
                        "snapshot": current.to_dict(),
                        "history": [item.to_dict() for item in copied_history],
                    },
                    ensure_ascii=False,
                    allow_nan=False,
                    separators=(",", ":"),
                ).encode("utf-8")
            )
        except (TypeError, ValueError, json.JSONDecodeError) as exc:
            return Result.err(
                _error(
                    "SESSION_VALUE_INVALID",
                    "Session history is not JSON serializable.",
                    reason=str(exc)[:256],
                )
            )
        if history_bytes > self.max_session_bytes:
            return Result.err(
                _error(
                    "SESSION_SIZE_EXCEEDED",
                    "Session history exceeds the configured byte limit.",
                    max_bytes=self.max_session_bytes,
                )
            )
        return Result.ok(tuple(copied_history))

    def _next_history(
        self,
        history: Tuple[SessionSnapshot, ...],
        candidate: SessionSnapshot,
    ) -> Result[Tuple[SessionSnapshot, ...], Error]:
        values = (history + (candidate,))[-self.max_history :]
        return self._validate_history(values, candidate)

    def _history_tail(
        self, history: Tuple[SessionSnapshot, ...], limit: Optional[int]
    ) -> Result[Tuple[SessionSnapshot, ...], Error]:
        limit_result = self._history_limit(self.max_history if limit is None else limit)
        if limit_result.is_err():
            return Result.err(limit_result.unwrap_err())
        if not history:
            return Result.err(
                _error("SESSION_HISTORY_INVALID", "Session history is empty.")
            )
        return Result.ok(tuple(history[-limit_result.unwrap() :]))

    def _select_fork_snapshot(
        self,
        current: SessionSnapshot,
        history: Tuple[SessionSnapshot, ...],
        at_version: Optional[int],
        expected_version: Optional[int],
    ) -> Result[SessionSnapshot, Error]:
        at_result = self._version(at_version, "at_version")
        if at_result.is_err():
            return Result.err(at_result.unwrap_err())
        expected_result = self._version(expected_version, "expected_version")
        if expected_result.is_err():
            return Result.err(expected_result.unwrap_err())
        expected = expected_result.unwrap()
        if expected is not None and expected != current.version:
            return Result.err(
                _error(
                    "SESSION_CONFLICT",
                    "Session version does not match.",
                    session_id=current.session_id,
                    expected_version=expected,
                    actual_version=current.version,
                )
            )
        requested = at_result.unwrap()
        selected_version = current.version if requested is None else requested
        for snapshot in history:
            if snapshot.version == selected_version:
                return self._copy_snapshot(snapshot)
        return Result.err(
            _error(
                "SESSION_VERSION_UNAVAILABLE",
                "The requested session version is not retained.",
                session_id=current.session_id,
                requested_version=selected_version,
                current_version=current.version,
            )
        )

    def _fork_snapshot(
        self, source: SessionSnapshot, new_session_id: str
    ) -> Result[SessionSnapshot, Error]:
        now = time.time()
        return self._copy_snapshot(
            SessionSnapshot(
                session_id=new_session_id,
                messages=source.messages,
                metadata=source.metadata,
                version=0,
                created_at=now,
                updated_at=now,
            )
        )

    def _message(self, message: SessionMessage) -> Result[SessionMessage, Error]:
        if not isinstance(message, SessionMessage):
            return Result.err(
                _error(
                    "SESSION_MESSAGE_INVALID",
                    "Session append requires a SessionMessage.",
                )
            )
        try:
            copied = SessionMessage.from_dict(message.to_dict())
        except (TypeError, ValueError, json.JSONDecodeError) as exc:
            return Result.err(
                _error(
                    "SESSION_MESSAGE_INVALID",
                    "Session message is invalid.",
                    reason=str(exc)[:256],
                )
            )
        size = len(json.dumps(copied.to_dict(), ensure_ascii=False).encode("utf-8"))
        if size > self.max_message_bytes:
            return Result.err(
                _error(
                    "SESSION_MESSAGE_SIZE",
                    "Session message exceeds the configured byte limit.",
                    max_bytes=self.max_message_bytes,
                )
            )
        return Result.ok(copied)

    def _new_snapshot(
        self, session_id: str, metadata: Optional[Mapping[str, Any]]
    ) -> Result[SessionSnapshot, Error]:
        metadata_result = self._metadata(metadata)
        if metadata_result.is_err():
            return Result.err(metadata_result.unwrap_err())
        now = time.time()
        return self._copy_snapshot(
            SessionSnapshot(
                session_id=session_id,
                metadata=metadata_result.unwrap(),
                created_at=now,
                updated_at=now,
            )
        )

    def _append_snapshot(
        self,
        current: SessionSnapshot,
        message: SessionMessage,
        expected_version: Optional[int],
    ) -> Result[SessionSnapshot, Error]:
        if expected_version is not None and expected_version != current.version:
            return Result.err(
                _error(
                    "SESSION_CONFLICT",
                    "Session version does not match.",
                    session_id=current.session_id,
                    expected_version=expected_version,
                    actual_version=current.version,
                )
            )
        message_result = self._message(message)
        if message_result.is_err():
            return Result.err(message_result.unwrap_err())
        if len(current.messages) >= self.max_messages:
            return Result.err(
                _error(
                    "SESSION_MESSAGE_LIMIT",
                    "Session has reached its message limit.",
                    max_messages=self.max_messages,
                )
            )
        if any(
            item.message_id == message_result.unwrap().message_id
            for item in current.messages
        ):
            return Result.err(
                _error(
                    "SESSION_MESSAGE_DUPLICATE",
                    "Message ID already exists in the session.",
                    message_id=message_result.unwrap().message_id,
                )
            )
        candidate = replace(
            current,
            messages=current.messages + (message_result.unwrap(),),
            version=current.version + 1,
            updated_at=time.time(),
        )
        return self._copy_snapshot(candidate)

    def _clear_snapshot(
        self, current: SessionSnapshot, expected_version: Optional[int]
    ) -> Result[SessionSnapshot, Error]:
        if expected_version is not None and expected_version != current.version:
            return Result.err(
                _error(
                    "SESSION_CONFLICT",
                    "Session version does not match.",
                    session_id=current.session_id,
                    expected_version=expected_version,
                    actual_version=current.version,
                )
            )
        return self._copy_snapshot(
            replace(
                current,
                messages=(),
                version=current.version + 1,
                updated_at=time.time(),
            )
        )

    def _compact_snapshot(
        self,
        current: SessionSnapshot,
        summary: str,
        keep_last: int,
        expected_version: Optional[int],
    ) -> Result[SessionSnapshot, Error]:
        if expected_version is not None and expected_version != current.version:
            return Result.err(
                _error(
                    "SESSION_CONFLICT",
                    "Session version does not match.",
                    session_id=current.session_id,
                    expected_version=expected_version,
                    actual_version=current.version,
                )
            )
        if not isinstance(keep_last, int) or isinstance(keep_last, bool):
            return Result.err(
                _error(
                    "SESSION_COMPACTION_LIMIT",
                    "keep_last must be a non-negative integer.",
                )
            )
        if keep_last < 0 or keep_last >= self.max_messages:
            return Result.err(
                _error(
                    "SESSION_COMPACTION_LIMIT",
                    "keep_last must leave room for the summary message.",
                    max_messages=self.max_messages,
                )
            )
        if not current.messages or keep_last >= len(current.messages):
            return Result.err(
                _error(
                    "SESSION_COMPACTION_NOOP",
                    "Compaction must remove at least one existing message.",
                    message_count=len(current.messages),
                    keep_last=keep_last,
                )
            )
        text_error = _valid_text(summary, "summary")
        if text_error:
            return Result.err(text_error)
        summary_message = SessionMessage(
            role=ChatRole.ASSISTANT.value,
            content=summary,
            metadata={
                "compaction": "host_summary",
                "dropped_messages": len(current.messages) - keep_last,
                "source_version": current.version,
            },
        )
        summary_result = self._message(summary_message)
        if summary_result.is_err():
            return Result.err(summary_result.unwrap_err())
        tail = current.messages[-keep_last:] if keep_last else ()
        return self._copy_snapshot(
            replace(
                current,
                messages=(summary_result.unwrap(),) + tuple(tail),
                version=current.version + 1,
                updated_at=time.time(),
            )
        )


class InMemorySessionStore(_SessionStoreSupport):
    """Thread-safe bounded session store for tests and local hosts."""

    def __init__(
        self,
        *,
        max_sessions: int = DEFAULT_MAX_SESSIONS,
        max_messages: int = DEFAULT_MAX_MESSAGES,
        max_message_bytes: int = DEFAULT_MAX_MESSAGE_BYTES,
        max_metadata_bytes: int = DEFAULT_MAX_METADATA_BYTES,
        max_session_bytes: int = DEFAULT_MAX_SESSION_BYTES,
        max_history: int = DEFAULT_MAX_HISTORY,
    ) -> None:
        self._configure_limits(
            max_sessions=max_sessions,
            max_messages=max_messages,
            max_message_bytes=max_message_bytes,
            max_metadata_bytes=max_metadata_bytes,
            max_session_bytes=max_session_bytes,
            max_history=max_history,
        )
        self._sessions: Dict[str, SessionSnapshot] = {}
        self._history: Dict[str, Tuple[SessionSnapshot, ...]] = {}
        self._lock = threading.RLock()

    def create(
        self,
        session_id: Optional[str] = None,
        *,
        metadata: Optional[Mapping[str, Any]] = None,
    ) -> Result[SessionSnapshot, Error]:
        resolved_id = (
            f"session-{uuid.uuid4().hex}" if session_id is None else session_id
        )
        id_result = self._session_id(resolved_id)
        if id_result.is_err():
            return Result.err(id_result.unwrap_err())
        with self._lock:
            if resolved_id in self._sessions:
                return Result.err(
                    _error(
                        "SESSION_EXISTS",
                        "A session with this ID already exists.",
                        session_id=resolved_id,
                    )
                )
            if len(self._sessions) >= self.max_sessions:
                return Result.err(
                    _error(
                        "SESSION_LIMIT",
                        "The session store has reached its session limit.",
                        max_sessions=self.max_sessions,
                    )
                )
            snapshot_result = self._new_snapshot(resolved_id, metadata)
            if snapshot_result.is_err():
                return Result.err(snapshot_result.unwrap_err())
            snapshot = snapshot_result.unwrap()
            history = self._validate_history((snapshot,), snapshot)
            if history.is_err():
                return Result.err(history.unwrap_err())
            snapshot = history.unwrap()[-1]
            self._sessions[resolved_id] = snapshot
            self._history[resolved_id] = history.unwrap()
            return Result.ok(self._copy_snapshot(snapshot).unwrap())

    def load(self, session_id: str) -> Result[Optional[SessionSnapshot], Error]:
        id_result = self._session_id(session_id)
        if id_result.is_err():
            return Result.err(id_result.unwrap_err())
        with self._lock:
            snapshot = self._sessions.get(session_id)
            if snapshot is None:
                return Result.ok(None)
            copied = self._copy_snapshot(snapshot)
            if copied.is_err():
                return Result.err(copied.unwrap_err())
            return Result.ok(copied.unwrap())

    def append(
        self,
        session_id: str,
        message: SessionMessage,
        *,
        expected_version: Optional[int] = None,
    ) -> Result[SessionSnapshot, Error]:
        id_result = self._session_id(session_id)
        if id_result.is_err():
            return Result.err(id_result.unwrap_err())
        with self._lock:
            current = self._sessions.get(session_id)
            if current is None:
                return Result.err(
                    _error(
                        "SESSION_NOT_FOUND",
                        "Session was not found.",
                        session_id=session_id,
                    )
                )
            candidate = self._append_snapshot(current, message, expected_version)
            if candidate.is_err():
                return Result.err(candidate.unwrap_err())
            next_history = self._next_history(
                self._history[session_id], candidate.unwrap()
            )
            if next_history.is_err():
                return Result.err(next_history.unwrap_err())
            self._sessions[session_id] = candidate.unwrap()
            self._history[session_id] = next_history.unwrap()
            return Result.ok(self._copy_snapshot(candidate.unwrap()).unwrap())

    def clear(
        self,
        session_id: str,
        *,
        expected_version: Optional[int] = None,
    ) -> Result[SessionSnapshot, Error]:
        id_result = self._session_id(session_id)
        if id_result.is_err():
            return Result.err(id_result.unwrap_err())
        with self._lock:
            current = self._sessions.get(session_id)
            if current is None:
                return Result.err(
                    _error(
                        "SESSION_NOT_FOUND",
                        "Session was not found.",
                        session_id=session_id,
                    )
                )
            candidate = self._clear_snapshot(current, expected_version)
            if candidate.is_err():
                return Result.err(candidate.unwrap_err())
            next_history = self._next_history(
                self._history[session_id], candidate.unwrap()
            )
            if next_history.is_err():
                return Result.err(next_history.unwrap_err())
            self._sessions[session_id] = candidate.unwrap()
            self._history[session_id] = next_history.unwrap()
            return Result.ok(self._copy_snapshot(candidate.unwrap()).unwrap())

    def compact(
        self,
        session_id: str,
        summary: str,
        *,
        keep_last: int = 8,
        expected_version: Optional[int] = None,
    ) -> Result[SessionSnapshot, Error]:
        id_result = self._session_id(session_id)
        if id_result.is_err():
            return Result.err(id_result.unwrap_err())
        with self._lock:
            current = self._sessions.get(session_id)
            if current is None:
                return Result.err(
                    _error(
                        "SESSION_NOT_FOUND",
                        "Session was not found.",
                        session_id=session_id,
                    )
                )
            candidate = self._compact_snapshot(
                current, summary, keep_last, expected_version
            )
            if candidate.is_err():
                return Result.err(candidate.unwrap_err())
            next_history = self._next_history(
                self._history[session_id], candidate.unwrap()
            )
            if next_history.is_err():
                return Result.err(next_history.unwrap_err())
            self._sessions[session_id] = candidate.unwrap()
            self._history[session_id] = next_history.unwrap()
            return Result.ok(self._copy_snapshot(candidate.unwrap()).unwrap())

    def history(
        self, session_id: str, *, limit: Optional[int] = None
    ) -> Result[Tuple[SessionSnapshot, ...], Error]:
        id_result = self._session_id(session_id)
        if id_result.is_err():
            return Result.err(id_result.unwrap_err())
        with self._lock:
            history = self._history.get(session_id)
            if history is None:
                return Result.err(
                    _error(
                        "SESSION_NOT_FOUND",
                        "Session was not found.",
                        session_id=session_id,
                    )
                )
            tail = self._history_tail(history, limit)
            if tail.is_err():
                return Result.err(tail.unwrap_err())
            copied: List[SessionSnapshot] = []
            for snapshot in tail.unwrap():
                value = self._copy_snapshot(snapshot)
                if value.is_err():
                    return Result.err(value.unwrap_err())
                copied.append(value.unwrap())
            return Result.ok(tuple(copied))

    def fork(
        self,
        session_id: str,
        new_session_id: Optional[str] = None,
        *,
        at_version: Optional[int] = None,
        expected_version: Optional[int] = None,
    ) -> Result[SessionSnapshot, Error]:
        source_result = self._session_id(session_id)
        if source_result.is_err():
            return Result.err(source_result.unwrap_err())
        resolved_id = (
            f"session-{uuid.uuid4().hex}" if new_session_id is None else new_session_id
        )
        target_result = self._session_id(resolved_id)
        if target_result.is_err():
            return Result.err(target_result.unwrap_err())
        with self._lock:
            current = self._sessions.get(session_id)
            if current is None:
                return Result.err(
                    _error(
                        "SESSION_NOT_FOUND",
                        "Session was not found.",
                        session_id=session_id,
                    )
                )
            if resolved_id in self._sessions:
                return Result.err(
                    _error(
                        "SESSION_EXISTS",
                        "A session with this ID already exists.",
                        session_id=resolved_id,
                    )
                )
            if len(self._sessions) >= self.max_sessions:
                return Result.err(
                    _error(
                        "SESSION_LIMIT",
                        "The session store has reached its session limit.",
                        max_sessions=self.max_sessions,
                    )
                )
            source = self._select_fork_snapshot(
                current,
                self._history[session_id],
                at_version,
                expected_version,
            )
            if source.is_err():
                return Result.err(source.unwrap_err())
            target = self._fork_snapshot(source.unwrap(), resolved_id)
            if target.is_err():
                return Result.err(target.unwrap_err())
            snapshot = target.unwrap()
            self._sessions[resolved_id] = snapshot
            self._history[resolved_id] = (snapshot,)
            return Result.ok(self._copy_snapshot(snapshot).unwrap())


class FileSessionStore(_SessionStoreSupport):
    """Atomic JSON-file session store, coordinated within one process."""

    def __init__(
        self,
        directory: Union[str, Path],
        *,
        max_sessions: int = DEFAULT_MAX_SESSIONS,
        max_messages: int = DEFAULT_MAX_MESSAGES,
        max_message_bytes: int = DEFAULT_MAX_MESSAGE_BYTES,
        max_metadata_bytes: int = DEFAULT_MAX_METADATA_BYTES,
        max_session_bytes: int = DEFAULT_MAX_SESSION_BYTES,
        max_history: int = DEFAULT_MAX_HISTORY,
    ) -> None:
        self._configure_limits(
            max_sessions=max_sessions,
            max_messages=max_messages,
            max_message_bytes=max_message_bytes,
            max_metadata_bytes=max_metadata_bytes,
            max_session_bytes=max_session_bytes,
            max_history=max_history,
        )
        self.directory = Path(directory).expanduser().resolve()
        self.directory.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()

    def _path(self, session_id: str) -> Path:
        id_error = _valid_identifier(session_id, "session_id")
        if id_error:
            raise ValueError(id_error["message"])
        path = (self.directory / f"{session_id}.json").resolve()
        if self.directory not in path.parents:
            raise ValueError("session path escapes the configured directory")
        return path

    def _read_unlocked(
        self, session_id: str
    ) -> Result[Optional[_StoredSession], Error]:
        try:
            path = self._path(session_id)
            if not path.exists():
                return Result.ok(None)
            if path.stat().st_size > self.max_session_bytes:
                return Result.err(
                    _error(
                        "SESSION_SIZE_EXCEEDED",
                        "Session exceeds the configured byte limit.",
                        max_bytes=self.max_session_bytes,
                    )
                )
            with path.open("r", encoding="utf-8") as handle:
                payload = json.load(handle)
            if not isinstance(payload, Mapping):
                raise ValueError("session record must be an object")
            if "schema_version" not in payload:
                snapshot = SessionSnapshot.from_dict(payload)
                history: Tuple[SessionSnapshot, ...] = (snapshot,)
            else:
                if payload.get("schema_version") != 2:
                    raise ValueError("unsupported session record schema")
                snapshot = SessionSnapshot.from_dict(payload["snapshot"])
                raw_history = payload.get("history")
                if not isinstance(raw_history, list):
                    raise ValueError("session history must be a list")
                history = tuple(SessionSnapshot.from_dict(item) for item in raw_history)
            validated = self._validate_history(
                history, snapshot, max_history=MAX_HISTORY
            )
            if validated.is_err():
                return Result.err(validated.unwrap_err())
            retained = validated.unwrap()[-self.max_history :]
            current = retained[-1]
            return Result.ok(_StoredSession(snapshot=current, history=retained))
        except (KeyError, OSError, TypeError, ValueError, json.JSONDecodeError) as exc:
            return Result.err(
                _error(
                    "SESSION_LOAD_ERROR",
                    "Failed to load session.",
                    reason=str(exc)[:256],
                )
            )

    def _write_unlocked(
        self,
        snapshot: SessionSnapshot,
        history: Tuple[SessionSnapshot, ...],
    ) -> Result[SessionSnapshot, Error]:
        validated = self._validate_history(history, snapshot)
        if validated.is_err():
            return Result.err(validated.unwrap_err())
        serialized = validated.unwrap()[-1]
        temporary_path: Optional[Path] = None
        try:
            payload = json.dumps(
                {
                    "schema_version": 2,
                    "snapshot": serialized.to_dict(),
                    "history": [item.to_dict() for item in validated.unwrap()],
                },
                ensure_ascii=False,
                allow_nan=False,
                indent=2,
            )
            if len(payload.encode("utf-8")) > self.max_session_bytes:
                return Result.err(
                    _error(
                        "SESSION_SIZE_EXCEEDED",
                        "Session history exceeds the configured byte limit.",
                        max_bytes=self.max_session_bytes,
                    )
                )
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                dir=str(self.directory),
                prefix=f".{snapshot.session_id}.",
                suffix=".tmp",
                delete=False,
            ) as handle:
                temporary_path = Path(handle.name)
                handle.write(payload)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(str(temporary_path), str(self._path(snapshot.session_id)))
            temporary_path = None
            return Result.ok(serialized)
        except (OSError, TypeError, ValueError, json.JSONDecodeError) as exc:
            return Result.err(
                _error(
                    "SESSION_SAVE_ERROR",
                    "Failed to save session.",
                    reason=str(exc)[:256],
                )
            )
        finally:
            if temporary_path is not None:
                try:
                    temporary_path.unlink()
                except OSError:
                    pass

    def create(
        self,
        session_id: Optional[str] = None,
        *,
        metadata: Optional[Mapping[str, Any]] = None,
    ) -> Result[SessionSnapshot, Error]:
        resolved_id = (
            f"session-{uuid.uuid4().hex}" if session_id is None else session_id
        )
        id_result = self._session_id(resolved_id)
        if id_result.is_err():
            return Result.err(id_result.unwrap_err())
        with self._lock:
            existing = self._read_unlocked(resolved_id)
            if existing.is_err():
                return Result.err(existing.unwrap_err())
            if existing.unwrap() is not None:
                return Result.err(
                    _error(
                        "SESSION_EXISTS",
                        "A session with this ID already exists.",
                        session_id=resolved_id,
                    )
                )
            try:
                session_count = sum(
                    1 for path in self.directory.glob("*.json") if path.is_file()
                )
            except OSError as exc:
                return Result.err(
                    _error(
                        "SESSION_SAVE_ERROR",
                        "Failed to inspect session store.",
                        reason=str(exc)[:256],
                    )
                )
            if session_count >= self.max_sessions:
                return Result.err(
                    _error(
                        "SESSION_LIMIT",
                        "The session store has reached its session limit.",
                        max_sessions=self.max_sessions,
                    )
                )
            snapshot = self._new_snapshot(resolved_id, metadata)
            if snapshot.is_err():
                return Result.err(snapshot.unwrap_err())
            created = snapshot.unwrap()
            return self._write_unlocked(created, (created,))

    def load(self, session_id: str) -> Result[Optional[SessionSnapshot], Error]:
        id_result = self._session_id(session_id)
        if id_result.is_err():
            return Result.err(id_result.unwrap_err())
        with self._lock:
            record = self._read_unlocked(session_id)
            if record.is_err():
                return Result.err(record.unwrap_err())
            stored = record.unwrap()
            if stored is None:
                return Result.ok(None)
            return Result.ok(stored.snapshot)

    def append(
        self,
        session_id: str,
        message: SessionMessage,
        *,
        expected_version: Optional[int] = None,
    ) -> Result[SessionSnapshot, Error]:
        id_result = self._session_id(session_id)
        if id_result.is_err():
            return Result.err(id_result.unwrap_err())
        with self._lock:
            current = self._read_unlocked(session_id)
            if current.is_err():
                return Result.err(current.unwrap_err())
            record = current.unwrap()
            if record is None:
                return Result.err(
                    _error(
                        "SESSION_NOT_FOUND",
                        "Session was not found.",
                        session_id=session_id,
                    )
                )
            current_snapshot = record.snapshot
            candidate = self._append_snapshot(
                current_snapshot, message, expected_version
            )
            if candidate.is_err():
                return Result.err(candidate.unwrap_err())
            next_history = self._next_history(record.history, candidate.unwrap())
            if next_history.is_err():
                return Result.err(next_history.unwrap_err())
            return self._write_unlocked(candidate.unwrap(), next_history.unwrap())

    def history(
        self, session_id: str, *, limit: Optional[int] = None
    ) -> Result[Tuple[SessionSnapshot, ...], Error]:
        id_result = self._session_id(session_id)
        if id_result.is_err():
            return Result.err(id_result.unwrap_err())
        with self._lock:
            record = self._read_unlocked(session_id)
            if record.is_err():
                return Result.err(record.unwrap_err())
            stored = record.unwrap()
            if stored is None:
                return Result.err(
                    _error(
                        "SESSION_NOT_FOUND",
                        "Session was not found.",
                        session_id=session_id,
                    )
                )
            tail = self._history_tail(stored.history, limit)
            if tail.is_err():
                return Result.err(tail.unwrap_err())
            return tail

    def fork(
        self,
        session_id: str,
        new_session_id: Optional[str] = None,
        *,
        at_version: Optional[int] = None,
        expected_version: Optional[int] = None,
    ) -> Result[SessionSnapshot, Error]:
        source_result = self._session_id(session_id)
        if source_result.is_err():
            return Result.err(source_result.unwrap_err())
        resolved_id = (
            f"session-{uuid.uuid4().hex}" if new_session_id is None else new_session_id
        )
        target_result = self._session_id(resolved_id)
        if target_result.is_err():
            return Result.err(target_result.unwrap_err())
        with self._lock:
            source_record = self._read_unlocked(session_id)
            if source_record.is_err():
                return Result.err(source_record.unwrap_err())
            source = source_record.unwrap()
            if source is None:
                return Result.err(
                    _error(
                        "SESSION_NOT_FOUND",
                        "Session was not found.",
                        session_id=session_id,
                    )
                )
            existing = self._read_unlocked(resolved_id)
            if existing.is_err():
                return Result.err(existing.unwrap_err())
            if existing.unwrap() is not None:
                return Result.err(
                    _error(
                        "SESSION_EXISTS",
                        "A session with this ID already exists.",
                        session_id=resolved_id,
                    )
                )
            try:
                session_count = sum(
                    1 for path in self.directory.glob("*.json") if path.is_file()
                )
            except OSError as exc:
                return Result.err(
                    _error(
                        "SESSION_SAVE_ERROR",
                        "Failed to inspect session store.",
                        reason=str(exc)[:256],
                    )
                )
            if session_count >= self.max_sessions:
                return Result.err(
                    _error(
                        "SESSION_LIMIT",
                        "The session store has reached its session limit.",
                        max_sessions=self.max_sessions,
                    )
                )
            selected = self._select_fork_snapshot(
                source.snapshot,
                source.history,
                at_version,
                expected_version,
            )
            if selected.is_err():
                return Result.err(selected.unwrap_err())
            target = self._fork_snapshot(selected.unwrap(), resolved_id)
            if target.is_err():
                return Result.err(target.unwrap_err())
            snapshot = target.unwrap()
            return self._write_unlocked(snapshot, (snapshot,))

    def clear(
        self,
        session_id: str,
        *,
        expected_version: Optional[int] = None,
    ) -> Result[SessionSnapshot, Error]:
        id_result = self._session_id(session_id)
        if id_result.is_err():
            return Result.err(id_result.unwrap_err())
        with self._lock:
            current = self._read_unlocked(session_id)
            if current.is_err():
                return Result.err(current.unwrap_err())
            record = current.unwrap()
            if record is None:
                return Result.err(
                    _error(
                        "SESSION_NOT_FOUND",
                        "Session was not found.",
                        session_id=session_id,
                    )
                )
            current_snapshot = record.snapshot
            candidate = self._clear_snapshot(current_snapshot, expected_version)
            if candidate.is_err():
                return Result.err(candidate.unwrap_err())
            next_history = self._next_history(record.history, candidate.unwrap())
            if next_history.is_err():
                return Result.err(next_history.unwrap_err())
            return self._write_unlocked(candidate.unwrap(), next_history.unwrap())

    def compact(
        self,
        session_id: str,
        summary: str,
        *,
        keep_last: int = 8,
        expected_version: Optional[int] = None,
    ) -> Result[SessionSnapshot, Error]:
        id_result = self._session_id(session_id)
        if id_result.is_err():
            return Result.err(id_result.unwrap_err())
        with self._lock:
            current = self._read_unlocked(session_id)
            if current.is_err():
                return Result.err(current.unwrap_err())
            record = current.unwrap()
            if record is None:
                return Result.err(
                    _error(
                        "SESSION_NOT_FOUND",
                        "Session was not found.",
                        session_id=session_id,
                    )
                )
            current_snapshot = record.snapshot
            candidate = self._compact_snapshot(
                current_snapshot, summary, keep_last, expected_version
            )
            if candidate.is_err():
                return Result.err(candidate.unwrap_err())
            next_history = self._next_history(record.history, candidate.unwrap())
            if next_history.is_err():
                return Result.err(next_history.unwrap_err())
            return self._write_unlocked(candidate.unwrap(), next_history.unwrap())


__all__ = [
    "DEFAULT_MAX_HISTORY",
    "DEFAULT_MAX_MESSAGES",
    "DEFAULT_MAX_MESSAGE_BYTES",
    "DEFAULT_MAX_METADATA_BYTES",
    "DEFAULT_MAX_SESSION_BYTES",
    "DEFAULT_MAX_SESSIONS",
    "FileSessionStore",
    "InMemorySessionStore",
    "MAX_HISTORY",
    "SessionCompactionStore",
    "SessionMessage",
    "SessionSnapshot",
    "SessionStore",
]
