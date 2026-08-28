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

# LLM types for MAPLE autonomy layer.

import base64
import binascii
import math
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Mapping, Optional, Tuple, Union
from urllib.parse import urlsplit

_MAX_CHAT_CONTENT_PARTS = 64
_MAX_CHAT_CONTENT_BYTES = 1 * 1024 * 1024
_MAX_IMAGE_SOURCE_BYTES = 1 * 1024 * 1024
_IMAGE_DATA_URI = re.compile(
    r"^data:(image/(?:jpeg|png|webp|gif));base64,([A-Za-z0-9+/]*={0,2})$"
)
_IMAGE_MIME_TYPES = {"image/jpeg", "image/png", "image/webp", "image/gif"}
_IMAGE_DETAILS = {"auto", "low", "high"}


class ChatRole(Enum):
    """Role of a message in a conversation."""

    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"


@dataclass(frozen=True)
class ImageContent:
    """A bounded image reference for multimodal chat messages.

    ``source`` is an HTTPS URL or a validated base64 data URI. MAPLE never
    fetches or executes the source; provider adapters decide which source
    forms they can transmit. Data URIs are portable to the built-in
    Anthropic adapter, while HTTPS URLs are supported by OpenAI-compatible
    adapters.
    """

    source: str
    mime_type: Optional[str] = None
    detail: str = "auto"

    def __post_init__(self) -> None:
        if not isinstance(self.source, str) or not self.source:
            raise ValueError("image source must be a non-empty string")
        if len(self.source.encode("utf-8")) > _MAX_IMAGE_SOURCE_BYTES:
            raise ValueError("image source exceeds the configured byte limit")
        if any(
            ord(character) < 32 or ord(character) == 127 for character in self.source
        ):
            raise ValueError("image source must not contain control characters")
        if self.detail not in _IMAGE_DETAILS:
            raise ValueError("image detail must be auto, low, or high")
        if self.mime_type is not None and self.mime_type not in _IMAGE_MIME_TYPES:
            raise ValueError("image mime_type must be a supported image type")

        if self.source.startswith("https://"):
            try:
                parsed = urlsplit(self.source)
            except ValueError as exc:
                raise ValueError("image source must be a valid HTTPS URL") from exc
            if parsed.hostname and parsed.username is None and parsed.password is None:
                return
            raise ValueError("image source must be a valid HTTPS URL")
        match = _IMAGE_DATA_URI.fullmatch(self.source)
        if match is None:
            if self.source.startswith("data:"):
                raise ValueError("image data URI is not valid base64 or is malformed")
            raise ValueError("image source must be an HTTPS URL or base64 data URI")
        data = match.group(2)
        try:
            decoded = base64.b64decode(data, validate=True)
        except (ValueError, binascii.Error) as exc:
            raise ValueError("image data URI is not valid base64") from exc
        if not decoded:
            raise ValueError("image data URI must contain image bytes")
        if len(decoded) > _MAX_IMAGE_SOURCE_BYTES:
            raise ValueError("image data exceeds the configured byte limit")
        if self.mime_type is not None and self.mime_type != match.group(1):
            raise ValueError("image mime_type does not match the data URI")


ContentPart = Union[str, ImageContent]
ChatContent = Union[str, List[ContentPart], Tuple[ContentPart, ...]]


def validate_chat_content(content: ChatContent) -> None:
    """Validate bounded text or multimodal chat content.

    The function raises ``ValueError`` for invalid caller-owned input so
    ``ChatMessage`` remains a small dataclass while providers can use the
    same contract at their boundary.
    """

    if isinstance(content, str):
        if len(content.encode("utf-8")) > _MAX_CHAT_CONTENT_BYTES:
            raise ValueError("chat content exceeds the configured byte limit")
        return
    if not isinstance(content, (list, tuple)):
        raise ValueError("chat content must be text or a list of content parts")
    if not content or len(content) > _MAX_CHAT_CONTENT_PARTS:
        raise ValueError("chat content must contain 1-64 parts")
    total_bytes = 0
    for part in content:
        if isinstance(part, str):
            total_bytes += len(part.encode("utf-8"))
        elif isinstance(part, ImageContent):
            total_bytes += len(part.source.encode("utf-8"))
        else:
            raise ValueError("chat content parts must be text or ImageContent")
    if total_bytes > _MAX_CHAT_CONTENT_BYTES:
        raise ValueError("chat content exceeds the configured byte limit")


@dataclass
class ToolDefinition:
    """Tool definition passed to LLM for function calling."""

    name: str
    description: str
    parameters: Dict[str, Any]  # JSON Schema


@dataclass
class ToolCall:
    """A tool call requested by the LLM."""

    id: str
    name: str
    arguments: Dict[str, Any]


@dataclass
class ToolResult:
    """Result of executing a tool call."""

    tool_call_id: str
    content: str
    is_error: bool = False


@dataclass
class ChatMessage:
    """A single message in a conversation."""

    role: ChatRole
    content: ChatContent
    name: Optional[str] = None
    tool_call_id: Optional[str] = None
    tool_calls: Optional[List[ToolCall]] = None

    def __post_init__(self) -> None:
        validate_chat_content(self.content)


@dataclass
class TokenUsage:
    """Token usage statistics."""

    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


@dataclass
class LLMResponse:
    """Response from an LLM provider."""

    content: Optional[str] = None
    tool_calls: List[ToolCall] = field(default_factory=list)
    usage: Optional[TokenUsage] = None
    model: str = ""
    finish_reason: str = ""
    raw_response: Optional[Any] = None
    request_id: Optional[str] = None


@dataclass
class LLMChunk:
    """A single chunk from a streaming LLM response."""

    content: str = ""
    tool_call_delta: Optional[Dict[str, Any]] = None
    finish_reason: Optional[str] = None
    usage: Optional[TokenUsage] = None
    request_id: Optional[str] = None


@dataclass
class LLMConfig:
    """Configuration for an LLM provider."""

    provider: str
    model: str
    api_key: Optional[str] = None
    api_base: Optional[str] = None
    temperature: float = 0.7
    max_tokens: int = 4096
    system_prompt: Optional[str] = None
    timeout: float = 120.0
    extra: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ModelRetryPolicy:
    """Bounded retry policy for classified model/provider failures.

    Retries are opt-in and apply only to exact ``errorType`` values listed in
    ``retryable_error_types``. This keeps authentication, validation, and
    other non-transient failures fail-fast while allowing hosts to choose a
    small amount of resilience for rate limits and temporary outages.
    """

    max_retries: int = 0
    base_delay_seconds: float = 0.0
    max_delay_seconds: float = 60.0
    retryable_error_types: Tuple[str, ...] = (
        "LLM_RATE_LIMITED",
        "LLM_TIMEOUT",
        "LLM_TRANSIENT_ERROR",
    )

    def __post_init__(self) -> None:
        if (
            not isinstance(self.max_retries, int)
            or isinstance(self.max_retries, bool)
            or not 0 <= self.max_retries <= 3
        ):
            raise ValueError("max_retries must be an integer from 0 to 3")
        for name, value in (
            ("base_delay_seconds", self.base_delay_seconds),
            ("max_delay_seconds", self.max_delay_seconds),
        ):
            if (
                isinstance(value, bool)
                or not isinstance(value, (int, float))
                or not math.isfinite(float(value))
                or value < 0
                or value > 60
            ):
                raise ValueError(f"{name} must be a finite number from 0 to 60")
        if self.max_delay_seconds < self.base_delay_seconds:
            raise ValueError("max_delay_seconds must be at least base_delay_seconds")
        if (
            not isinstance(self.retryable_error_types, tuple)
            or not self.retryable_error_types
            or len(self.retryable_error_types) > 16
        ):
            raise ValueError("retryable_error_types must be a tuple of 1 to 16 values")
        for error_type in self.retryable_error_types:
            if (
                not isinstance(error_type, str)
                or not error_type
                or len(error_type) > 64
                or any(
                    not (character.isupper() or character.isdigit() or character == "_")
                    for character in error_type
                )
            ):
                raise ValueError(
                    "retryable_error_types must contain bounded uppercase identifiers"
                )

    def delay_for_retry(self, retry_number: int) -> float:
        """Return the capped delay before a one-based retry attempt."""
        if (
            not isinstance(retry_number, int)
            or isinstance(retry_number, bool)
            or not 1 <= retry_number <= self.max_retries
        ):
            raise ValueError("retry_number must be within the configured retry limit")
        return min(
            float(self.max_delay_seconds),
            float(self.base_delay_seconds) * float(2 ** (retry_number - 1)),
        )

    def is_retryable(self, error: Mapping[str, Any]) -> bool:
        """Return whether an error has an explicitly retryable type."""
        return error.get("errorType") in self.retryable_error_types
