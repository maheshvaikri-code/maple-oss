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
"""Abstract LLM provider base class."""

import json
from abc import ABC, abstractmethod
from typing import (
    Any,
    AsyncIterator,
    Callable,
    Dict,
    Iterator,
    List,
    Mapping,
    Optional,
    Tuple,
)

from ..core.result import Result
from .types import (
    ChatMessage,
    LLMChunk,
    LLMConfig,
    LLMResponse,
    TokenUsage,
    ToolCall,
    ToolDefinition,
)

_MAX_STREAM_CONTENT_BYTES = 1_048_576
_MAX_STREAM_CHUNK_BYTES = 65_536
_MAX_STREAM_TOOL_CALLS = 64
_MAX_STREAM_ARGUMENT_BYTES = 262_144
_MAX_STREAM_FINISH_REASON_LENGTH = 128
_MAX_PROVIDER_USAGE_TOKENS = 100_000_000
_MAX_PROVIDER_MODEL_LENGTH = 256


class ProviderResponseError(ValueError):
    """Raised internally when an SDK response violates MAPLE's contract."""


def classify_provider_exception(exc: BaseException, *, fallback: str) -> str:
    """Map common provider failures to bounded, retry-aware error types.

    Classification is intentionally conservative: unknown exceptions retain
    the provider operation's existing fallback type. Wrapped stream errors
    inspect their direct cause so native provider exceptions are not hidden by
    an adapter wrapper.
    """
    cause = getattr(exc, "__cause__", None)
    if isinstance(cause, BaseException) and cause is not exc:
        classified = classify_provider_exception(cause, fallback=fallback)
        if classified != fallback:
            return classified

    status: Any = getattr(exc, "status_code", None)
    if status is None:
        status = getattr(exc, "status", None)
    if isinstance(status, bool) or not isinstance(status, int):
        status = None
    name = type(exc).__name__.casefold().replace("_", "")
    if status == 429 or any(
        marker in name for marker in ("ratelimit", "toomanyrequests")
    ):
        return "LLM_RATE_LIMITED"
    if (
        status == 408
        or isinstance(exc, TimeoutError)
        or any(marker in name for marker in ("timeout", "timedout"))
    ):
        return "LLM_TIMEOUT"
    if status is not None and 500 <= status <= 599:
        return "LLM_TRANSIENT_ERROR"
    if any(
        marker in name
        for marker in (
            "connection",
            "serviceunavailable",
            "internalserver",
            "badgateway",
            "temporarilyunavailable",
            "overloaded",
        )
    ):
        return "LLM_TRANSIENT_ERROR"
    return fallback


class LLMProvider(ABC):
    """
    Abstract base class for LLM providers.
    All methods return Result<T,E> following MAPLE conventions.
    """

    def __init__(self, config: LLMConfig):
        self.config = config
        self._total_prompt_tokens = 0
        self._total_completion_tokens = 0
        self._total_cost = 0.0

    @abstractmethod
    def complete(
        self,
        messages: List[ChatMessage],
        tools: Optional[List[ToolDefinition]] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        stop: Optional[List[str]] = None,
    ) -> Result["LLMResponse", Dict[str, Any]]:
        """Send a completion request to the LLM."""
        ...

    async def complete_async(
        self,
        messages: List[ChatMessage],
        tools: Optional[List[ToolDefinition]] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        stop: Optional[List[str]] = None,
    ) -> Result["LLMResponse", Dict[str, Any]]:
        """Async version of complete(). Default delegates to sync."""
        return self.complete(messages, tools, temperature, max_tokens, stop)

    async def stream(
        self,
        messages: List[ChatMessage],
        tools: Optional[List[ToolDefinition]] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> Result[AsyncIterator["LLMChunk"], Dict[str, Any]]:
        """Return bounded chunks, with native providers free to override.

        The base implementation is a compatibility stream: it completes the
        request first and then yields text/tool-call/finish chunks. It gives
        consumers one async contract without claiming provider-native
        first-token latency. Providers with real streaming transports should
        override this method.
        """
        completion = await self.complete_async(
            messages,
            tools=tools,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        if completion.is_err():
            return Result.err(completion.unwrap_err())
        response = completion.unwrap()

        async def _chunks() -> AsyncIterator[LLMChunk]:
            content = response.content or ""
            for text in self._bounded_text_chunks(content):
                yield LLMChunk(content=text)
            for tool_call in response.tool_calls:
                yield LLMChunk(
                    tool_call_delta={
                        "id": tool_call.id,
                        "name": tool_call.name,
                        "arguments": tool_call.arguments,
                    }
                )
            yield LLMChunk(
                finish_reason=response.finish_reason or None,
                usage=response.usage,
                request_id=response.request_id,
            )

        return Result.ok(_chunks())

    async def complete_from_stream(
        self,
        messages: List[ChatMessage],
        tools: Optional[List[ToolDefinition]] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        on_chunk: Optional[Callable[[LLMChunk], None]] = None,
    ) -> Result[LLMResponse, Dict[str, Any]]:
        """Aggregate bounded stream chunks into one agent-compatible response.

        The optional callback observes validated chunks before the final
        response is returned. Callback failures are isolated because callers
        commonly use it for telemetry. Provider selection, retry policy, and
        persistence remain outside this collector.
        """
        if on_chunk is not None and not callable(on_chunk):
            return Result.err(
                {
                    "errorType": "LLM_STREAM_INPUT_INVALID",
                    "message": "on_chunk must be callable when provided.",
                }
            )
        try:
            stream_result = await self.stream(
                messages,
                tools=tools,
                temperature=temperature,
                max_tokens=max_tokens,
            )
        except Exception as exc:
            return Result.err(
                {
                    "errorType": classify_provider_exception(
                        exc, fallback="LLM_STREAM_ERROR"
                    ),
                    "message": "provider stream could not be opened.",
                    "details": {"exception": type(exc).__name__},
                }
            )
        if stream_result.is_err():
            return Result.err(stream_result.unwrap_err())

        content_parts: List[str] = []
        content_bytes = 0
        tool_buffers: List[Dict[str, Any]] = []
        active_tool_index: Optional[int] = None
        finish_reason = ""
        usage: Optional[TokenUsage] = None
        request_id: Optional[str] = None

        def stream_error(error_type: str, message: str) -> Result[Any, Dict[str, Any]]:
            return Result.err({"errorType": error_type, "message": message})

        try:
            async for chunk in stream_result.unwrap():
                if not isinstance(chunk, LLMChunk):
                    return stream_error(
                        "LLM_STREAM_CHUNK_INVALID",
                        "provider stream yielded an invalid chunk.",
                    )
                if not isinstance(chunk.content, str):
                    return stream_error(
                        "LLM_STREAM_CHUNK_INVALID",
                        "provider chunk content must be text.",
                    )
                chunk_bytes = len(chunk.content.encode("utf-8"))
                if chunk_bytes > _MAX_STREAM_CHUNK_BYTES:
                    return stream_error(
                        "LLM_STREAM_CHUNK_TOO_LARGE",
                        "provider chunk content exceeds the byte limit.",
                    )
                content_bytes += chunk_bytes
                if content_bytes > _MAX_STREAM_CONTENT_BYTES:
                    return stream_error(
                        "LLM_STREAM_CONTENT_TOO_LARGE",
                        "provider stream content exceeds the byte limit.",
                    )
                if chunk.content:
                    content_parts.append(chunk.content)

                if chunk.finish_reason is not None:
                    if (
                        not isinstance(chunk.finish_reason, str)
                        or not chunk.finish_reason
                        or len(chunk.finish_reason) > _MAX_STREAM_FINISH_REASON_LENGTH
                        or any(ord(char) < 32 for char in chunk.finish_reason)
                    ):
                        return stream_error(
                            "LLM_STREAM_CHUNK_INVALID",
                            "provider finish reason is invalid.",
                        )
                    finish_reason = chunk.finish_reason

                usage = self._merge_stream_usage(usage, chunk.usage)
                if chunk.request_id is not None:
                    bounded_request_id = self._bounded_request_id(chunk.request_id)
                    if bounded_request_id is not None:
                        request_id = bounded_request_id

                delta = chunk.tool_call_delta
                if delta is not None:
                    if not isinstance(delta, Mapping):
                        return stream_error(
                            "LLM_STREAM_TOOL_CALL_INVALID",
                            "provider tool-call delta must be an object.",
                        )
                    raw_index = delta.get("index")
                    if raw_index is not None and (
                        not isinstance(raw_index, int)
                        or isinstance(raw_index, bool)
                        or raw_index < 0
                        or raw_index >= _MAX_STREAM_TOOL_CALLS
                    ):
                        return stream_error(
                            "LLM_STREAM_TOOL_CALL_INVALID",
                            "provider tool-call index is invalid.",
                        )
                    raw_id = delta.get("id")
                    if raw_id is not None and (
                        not isinstance(raw_id, str)
                        or not raw_id
                        or len(raw_id) > 256
                        or any(ord(char) < 32 for char in raw_id)
                    ):
                        return stream_error(
                            "LLM_STREAM_TOOL_CALL_INVALID",
                            "provider tool-call ID is invalid.",
                        )
                    raw_name = delta.get("name")
                    if raw_name is not None and (
                        not isinstance(raw_name, str)
                        or not raw_name
                        or len(raw_name) > 256
                        or any(ord(char) < 32 for char in raw_name)
                    ):
                        return stream_error(
                            "LLM_STREAM_TOOL_CALL_INVALID",
                            "provider tool name is invalid.",
                        )

                    selected_index: Optional[int] = raw_index
                    if selected_index is None and isinstance(raw_id, str):
                        selected_index = next(
                            (
                                index
                                for index, candidate in enumerate(tool_buffers)
                                if candidate.get("id") == raw_id
                            ),
                            None,
                        )
                    if selected_index is None and raw_id is None:
                        selected_index = active_tool_index
                    if selected_index is None:
                        selected_index = len(tool_buffers)
                    if selected_index > len(tool_buffers):
                        return stream_error(
                            "LLM_STREAM_TOOL_CALL_INVALID",
                            "provider tool-call index skipped a call.",
                        )
                    if selected_index == len(tool_buffers):
                        if len(tool_buffers) >= _MAX_STREAM_TOOL_CALLS:
                            return stream_error(
                                "LLM_STREAM_TOOL_CALL_LIMIT",
                                "provider stream exceeded the tool-call limit.",
                            )
                        tool_buffers.append(
                            {
                                "id": None,
                                "name": None,
                                "argument_text": None,
                                "argument_value": {},
                            }
                        )
                    active_tool_index = selected_index
                    buffer = tool_buffers[selected_index]
                    if raw_id is not None:
                        if buffer["id"] is not None and buffer["id"] != raw_id:
                            return stream_error(
                                "LLM_STREAM_TOOL_CALL_INVALID",
                                "provider changed a tool-call ID mid-stream.",
                            )
                        buffer["id"] = raw_id
                    if raw_name is not None:
                        if buffer["name"] is not None and buffer["name"] != raw_name:
                            return stream_error(
                                "LLM_STREAM_TOOL_CALL_INVALID",
                                "provider changed a tool name mid-stream.",
                            )
                        buffer["name"] = raw_name
                    raw_arguments = delta.get("arguments")
                    if raw_arguments is not None:
                        if isinstance(raw_arguments, str):
                            argument_bytes = len(raw_arguments.encode("utf-8"))
                            existing_text = buffer["argument_text"] or ""
                            if (
                                buffer["argument_value"]
                                or len(existing_text.encode("utf-8")) + argument_bytes
                                > _MAX_STREAM_ARGUMENT_BYTES
                            ):
                                return stream_error(
                                    "LLM_STREAM_TOOL_ARGUMENTS_TOO_LARGE",
                                    "provider tool arguments exceed the byte limit.",
                                )
                            buffer["argument_text"] = existing_text + raw_arguments
                        elif isinstance(raw_arguments, Mapping):
                            if buffer["argument_text"] is not None:
                                return stream_error(
                                    "LLM_STREAM_TOOL_CALL_INVALID",
                                    "provider mixed tool argument formats.",
                                )
                            buffer["argument_value"].update(dict(raw_arguments))
                            try:
                                if (
                                    len(
                                        json.dumps(
                                            buffer["argument_value"],
                                            allow_nan=False,
                                        ).encode("utf-8")
                                    )
                                    > _MAX_STREAM_ARGUMENT_BYTES
                                ):
                                    return stream_error(
                                        "LLM_STREAM_TOOL_ARGUMENTS_TOO_LARGE",
                                        (
                                            "provider tool arguments exceed the byte "
                                            "limit."
                                        ),
                                    )
                            except (TypeError, ValueError, OverflowError):
                                return stream_error(
                                    "LLM_STREAM_TOOL_CALL_INVALID",
                                    "provider tool arguments must be JSON-compatible.",
                                )
                        else:
                            return stream_error(
                                "LLM_STREAM_TOOL_CALL_INVALID",
                                "provider tool arguments must be text or an object.",
                            )

                if on_chunk is not None:
                    try:
                        on_chunk(chunk)
                    except Exception:
                        pass
        except Exception as exc:
            return Result.err(
                {
                    "errorType": "LLM_STREAM_ERROR",
                    "message": "provider stream iteration failed.",
                    "details": {"exception": type(exc).__name__},
                }
            )

        tool_calls: List[ToolCall] = []
        for buffer in tool_buffers:
            if not isinstance(buffer["id"], str) or not isinstance(buffer["name"], str):
                return stream_error(
                    "LLM_STREAM_TOOL_CALL_INVALID",
                    "provider tool call is missing an ID or name.",
                )
            if buffer["argument_text"] is not None:
                try:
                    parsed_arguments = json.loads(buffer["argument_text"] or "{}")
                except (TypeError, ValueError, json.JSONDecodeError):
                    return stream_error(
                        "LLM_STREAM_TOOL_ARGUMENTS_INVALID",
                        "provider tool arguments are not valid JSON.",
                    )
                if not isinstance(parsed_arguments, dict):
                    return stream_error(
                        "LLM_STREAM_TOOL_ARGUMENTS_INVALID",
                        "provider tool arguments must decode to an object.",
                    )
                arguments = parsed_arguments
            else:
                arguments = buffer["argument_value"]
            tool_calls.append(
                ToolCall(
                    id=buffer["id"],
                    name=buffer["name"],
                    arguments=arguments,
                )
            )
        response = LLMResponse(
            content="".join(content_parts) or None,
            tool_calls=tool_calls,
            usage=usage,
            model=self.config.model,
            finish_reason=finish_reason,
            request_id=request_id,
        )
        return Result.ok(response)

    @staticmethod
    def _bounded_text_chunks(content: str) -> Iterator[str]:
        """Split provider text into bounded chunks for the shared contract."""
        for offset in range(0, len(content), 256):
            yield content[offset : offset + 256]

    def count_tokens(self, text: str) -> int:
        """Estimate token count (provider-specific override recommended)."""
        return len(text) // 4

    @staticmethod
    def _bounded_request_id(value: Any) -> Optional[str]:
        """Accept only a small, non-sensitive provider correlation ID."""
        if (
            not isinstance(value, str)
            or not value
            or len(value) > 256
            or any(ord(char) < 32 for char in value)
        ):
            return None
        return value

    @staticmethod
    def _stream_usage_parts(
        value: Any,
    ) -> Optional[Tuple[Optional[int], Optional[int], Optional[int]]]:
        """Read bounded usage fields from SDK objects or mapping fixtures."""
        if value is None:
            return None

        def read(*names: str) -> Any:
            if isinstance(value, Mapping):
                for name in names:
                    if name in value:
                        return value[name]
                return None
            for name in names:
                candidate = getattr(value, name, None)
                if candidate is not None:
                    return candidate
            return None

        prompt_tokens = read("prompt_tokens", "input_tokens")
        completion_tokens = read("completion_tokens", "output_tokens")
        total_tokens = read("total_tokens")
        fields = (prompt_tokens, completion_tokens, total_tokens)
        if all(field is None for field in fields):
            return None
        if any(
            not isinstance(field, int) or isinstance(field, bool) or field < 0
            for field in fields
            if field is not None
        ):
            return None
        if any(
            field is not None and field > _MAX_PROVIDER_USAGE_TOKENS for field in fields
        ):
            return None
        return prompt_tokens, completion_tokens, total_tokens

    @classmethod
    def _parse_completion_usage(cls, value: Any) -> Optional[TokenUsage]:
        """Parse complete-response usage, rejecting partial or invalid fields."""
        if value is None:
            return None
        parts = cls._stream_usage_parts(value)
        if parts is None or parts[0] is None or parts[1] is None:
            raise ProviderResponseError("provider usage metadata is invalid")
        total_tokens = parts[2]
        if total_tokens is None:
            total_tokens = parts[0] + parts[1]
        return TokenUsage(
            prompt_tokens=parts[0],
            completion_tokens=parts[1],
            total_tokens=total_tokens,
        )

    @staticmethod
    def _validate_completion_response(response: Any) -> LLMResponse:
        """Validate normalized provider output before it reaches callers."""
        if not isinstance(response, LLMResponse):
            raise ProviderResponseError("provider response is not an LLMResponse")
        if response.content is not None:
            if not isinstance(response.content, str):
                raise ProviderResponseError("provider response content is invalid")
            try:
                content_bytes = len(response.content.encode("utf-8"))
            except UnicodeError as exc:
                raise ProviderResponseError(
                    "provider response content is not valid UTF-8"
                ) from exc
            if content_bytes > _MAX_STREAM_CONTENT_BYTES:
                raise ProviderResponseError("provider response content is too large")
        if (
            not isinstance(response.model, str)
            or len(response.model) > _MAX_PROVIDER_MODEL_LENGTH
        ):
            raise ProviderResponseError("provider response model is invalid")
        if response.finish_reason is not None:
            if (
                not isinstance(response.finish_reason, str)
                or len(response.finish_reason) > _MAX_STREAM_FINISH_REASON_LENGTH
                or any(
                    ord(char) < 32 or ord(char) == 127
                    for char in response.finish_reason
                )
            ):
                raise ProviderResponseError(
                    "provider response finish reason is invalid"
                )
        if response.request_id is not None:
            if (
                not isinstance(response.request_id, str)
                or len(response.request_id) > 256
                or any(
                    ord(char) < 32 or ord(char) == 127 for char in response.request_id
                )
            ):
                raise ProviderResponseError("provider response request ID is invalid")
        if (
            not isinstance(response.tool_calls, list)
            or len(response.tool_calls) > _MAX_STREAM_TOOL_CALLS
        ):
            raise ProviderResponseError("provider response tool calls are invalid")
        for tool_call in response.tool_calls:
            if not isinstance(tool_call, ToolCall):
                raise ProviderResponseError("provider response tool call is invalid")
            if (
                not isinstance(tool_call.id, str)
                or not tool_call.id
                or len(tool_call.id) > 256
                or any(ord(char) < 32 or ord(char) == 127 for char in tool_call.id)
            ):
                raise ProviderResponseError("provider response tool call ID is invalid")
            if (
                not isinstance(tool_call.name, str)
                or not tool_call.name
                or len(tool_call.name) > 256
                or any(ord(char) < 32 or ord(char) == 127 for char in tool_call.name)
            ):
                raise ProviderResponseError("provider response tool name is invalid")
            if not isinstance(tool_call.arguments, dict):
                raise ProviderResponseError("provider tool arguments must be an object")
            try:
                encoded_arguments = json.dumps(
                    tool_call.arguments,
                    ensure_ascii=False,
                    allow_nan=False,
                    separators=(",", ":"),
                )
                normalized_arguments = json.loads(encoded_arguments)
                if normalized_arguments != tool_call.arguments:
                    raise ValueError("provider tool arguments are not JSON-native")
                argument_bytes = len(encoded_arguments.encode("utf-8"))
            except (
                TypeError,
                ValueError,
                OverflowError,
                RecursionError,
                UnicodeError,
            ) as exc:
                raise ProviderResponseError(
                    "provider tool arguments are not JSON"
                ) from exc
            if argument_bytes > _MAX_STREAM_ARGUMENT_BYTES:
                raise ProviderResponseError("provider tool arguments are too large")
        if response.usage is not None:
            if not isinstance(response.usage, TokenUsage):
                raise ProviderResponseError("provider response usage is invalid")
            usage_fields = (
                response.usage.prompt_tokens,
                response.usage.completion_tokens,
                response.usage.total_tokens,
            )
            if any(
                not isinstance(field, int)
                or isinstance(field, bool)
                or not 0 <= field <= _MAX_PROVIDER_USAGE_TOKENS
                for field in usage_fields
            ):
                raise ProviderResponseError("provider response usage is invalid")
        return response

    @classmethod
    def _merge_stream_usage(
        cls, current: Optional[TokenUsage], value: Any
    ) -> Optional[TokenUsage]:
        """Merge partial provider usage events into one final trailer."""
        parts = cls._stream_usage_parts(value)
        if parts is None:
            return current
        prompt_tokens = current.prompt_tokens if current is not None else 0
        completion_tokens = current.completion_tokens if current is not None else 0
        if parts[0] is not None:
            prompt_tokens = parts[0]
        if parts[1] is not None:
            completion_tokens = parts[1]
        total_tokens = parts[2]
        if total_tokens is None:
            total_tokens = prompt_tokens + completion_tokens
        return TokenUsage(
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
        )

    def get_usage_stats(self) -> Dict[str, Any]:
        """Get cumulative usage statistics."""
        return {
            "total_prompt_tokens": self._total_prompt_tokens,
            "total_completion_tokens": self._total_completion_tokens,
            "total_cost_usd": self._total_cost,
            "provider": self.config.provider,
            "model": self.config.model,
        }

    def _track_usage(self, response: LLMResponse) -> None:
        """Track token usage from a response."""
        if response.usage:
            self._total_prompt_tokens += response.usage.prompt_tokens
            self._total_completion_tokens += response.usage.completion_tokens
