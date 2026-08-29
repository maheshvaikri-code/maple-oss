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
"""Anthropic Claude LLM provider."""

import logging
from typing import Any, AsyncIterator, Dict, List, Optional, Tuple, cast

from ..core.result import Result
from .provider import (
    LLMProvider,
    ProviderResponseError,
    classify_provider_exception,
)
from .types import (
    ChatContent,
    ChatMessage,
    ChatRole,
    ImageContent,
    LLMChunk,
    LLMConfig,
    LLMResponse,
    ToolCall,
    ToolDefinition,
)

logger = logging.getLogger(__name__)


class AnthropicProvider(LLMProvider):
    """Anthropic Claude API provider."""

    def __init__(self, config: LLMConfig):
        super().__init__(config)
        self.client = None
        self.async_client = None
        try:
            import anthropic

            client_kwargs: Dict[str, Any] = {}
            if config.api_key:
                client_kwargs["api_key"] = config.api_key
            if config.api_base:
                client_kwargs["base_url"] = config.api_base
            if config.timeout:
                client_kwargs["timeout"] = config.timeout
            self.client = cast(Any, anthropic.Anthropic)(**client_kwargs)
            async_client_type = getattr(anthropic, "AsyncAnthropic", None)
            if async_client_type is not None:
                self.async_client = cast(Any, async_client_type)(**client_kwargs)
        except ImportError:
            logger.warning(
                "anthropic library not installed. Install with: "
                "pip install anthropic"
            )

    def complete(
        self,
        messages: List[ChatMessage],
        tools: Optional[List[ToolDefinition]] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        stop: Optional[List[str]] = None,
    ) -> Result[LLMResponse, Dict[str, Any]]:
        if not self.client:
            return Result.err(
                {
                    "errorType": "PROVIDER_NOT_AVAILABLE",
                    "message": (
                        "anthropic library not installed. Install with: "
                        "pip install anthropic"
                    ),
                }
            )
        formatted = self._format_messages(messages)
        if formatted.is_err():
            return Result.err(formatted.unwrap_err())
        system_prompt, conversation = formatted.unwrap()
        try:

            kwargs: Dict[str, Any] = {
                "model": self.config.model,
                "messages": conversation,
                "max_tokens": max_tokens or self.config.max_tokens,
                "temperature": (
                    temperature if temperature is not None else self.config.temperature
                ),
            }
            if system_prompt:
                kwargs["system"] = system_prompt
            if stop:
                kwargs["stop_sequences"] = stop
            if tools:
                kwargs["tools"] = [self._format_tool(t) for t in tools]

            response = self.client.messages.create(**kwargs)
            llm_response = self._validate_completion_response(
                self._parse_response(response)
            )
            self._track_usage(llm_response)
            return Result.ok(llm_response)
        except ProviderResponseError:
            return Result.err(
                {
                    "errorType": "LLM_PROVIDER_RESPONSE_INVALID",
                    "message": (
                        "Anthropic provider returned an invalid completion " "response."
                    ),
                }
            )
        except Exception as e:
            return Result.err(
                {
                    "errorType": classify_provider_exception(
                        e, fallback="LLM_COMPLETION_ERROR"
                    ),
                    "message": f"Anthropic completion failed: {str(e)}",
                }
            )

    async def complete_async(
        self,
        messages: List[ChatMessage],
        tools: Optional[List[ToolDefinition]] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        stop: Optional[List[str]] = None,
    ) -> Result[LLMResponse, Dict[str, Any]]:
        """Complete through the native async Anthropic client."""

        if not self.async_client:
            return await super().complete_async(
                messages,
                tools=tools,
                temperature=temperature,
                max_tokens=max_tokens,
                stop=stop,
            )
        formatted = self._format_messages(messages)
        if formatted.is_err():
            return Result.err(formatted.unwrap_err())
        system_prompt, conversation = formatted.unwrap()
        try:
            kwargs: Dict[str, Any] = {
                "model": self.config.model,
                "messages": conversation,
                "max_tokens": max_tokens or self.config.max_tokens,
                "temperature": (
                    temperature if temperature is not None else self.config.temperature
                ),
            }
            if system_prompt:
                kwargs["system"] = system_prompt
            if stop:
                kwargs["stop_sequences"] = stop
            if tools:
                kwargs["tools"] = [self._format_tool(tool) for tool in tools]
            response = await cast(Any, self.async_client).messages.create(**kwargs)
            llm_response = self._validate_completion_response(
                self._parse_response(response)
            )
            self._track_usage(llm_response)
            return Result.ok(llm_response)
        except ProviderResponseError:
            return Result.err(
                {
                    "errorType": "LLM_PROVIDER_RESPONSE_INVALID",
                    "message": (
                        "Anthropic provider returned an invalid completion " "response."
                    ),
                }
            )
        except Exception as exc:
            return Result.err(
                {
                    "errorType": classify_provider_exception(
                        exc, fallback="LLM_COMPLETION_ERROR"
                    ),
                    "message": "Anthropic async completion failed.",
                    "details": {"exception": type(exc).__name__},
                }
            )

    async def stream(
        self,
        messages: List[ChatMessage],
        tools: Optional[List[ToolDefinition]] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> Result[AsyncIterator[LLMChunk], Dict[str, Any]]:
        """Return native Anthropic Messages API streaming deltas."""
        if not self.async_client:
            return await super().stream(
                messages,
                tools=tools,
                temperature=temperature,
                max_tokens=max_tokens,
            )

        formatted = self._format_messages(messages)
        if formatted.is_err():
            return Result.err(formatted.unwrap_err())
        system_prompt, conversation = formatted.unwrap()

        kwargs: Dict[str, Any] = {
            "model": self.config.model,
            "messages": conversation,
            "max_tokens": max_tokens or self.config.max_tokens,
            "temperature": (
                temperature if temperature is not None else self.config.temperature
            ),
            "stream": True,
        }
        if system_prompt:
            kwargs["system"] = system_prompt
        if tools:
            kwargs["tools"] = [self._format_tool(t) for t in tools]

        try:
            response_stream = await self.async_client.messages.create(**kwargs)
        except Exception as e:
            return Result.err(
                {
                    "errorType": classify_provider_exception(
                        e, fallback="LLM_STREAM_ERROR"
                    ),
                    "message": f"Anthropic streaming failed: {str(e)}",
                }
            )

        async def _chunks() -> AsyncIterator[LLMChunk]:
            finish_reason = None
            request_id = None
            usage = None
            try:
                async for event in response_stream:
                    event_type = getattr(event, "type", "")
                    request_id = (
                        self._bounded_request_id(getattr(event, "id", None))
                        or request_id
                    )
                    if event_type == "message_start":
                        message = getattr(event, "message", None)
                        request_id = (
                            self._bounded_request_id(getattr(message, "id", None))
                            or request_id
                        )
                        usage = self._merge_stream_usage(
                            usage, getattr(message, "usage", None)
                        )
                    elif event_type == "content_block_start":
                        block = getattr(event, "content_block", None)
                        if getattr(block, "type", None) == "tool_use":
                            yield LLMChunk(
                                tool_call_delta={
                                    "id": getattr(block, "id", None),
                                    "name": getattr(block, "name", None),
                                    "arguments": {},
                                }
                            )
                    elif event_type == "content_block_delta":
                        delta = getattr(event, "delta", None)
                        delta_type = getattr(delta, "type", "")
                        if delta_type == "text_delta":
                            for text in self._bounded_text_chunks(
                                getattr(delta, "text", "") or ""
                            ):
                                yield LLMChunk(content=text)
                        elif delta_type == "input_json_delta":
                            yield LLMChunk(
                                tool_call_delta={
                                    "arguments": getattr(delta, "partial_json", "")
                                    or "",
                                }
                            )
                    elif event_type == "message_delta":
                        delta = getattr(event, "delta", None)
                        usage = self._merge_stream_usage(
                            usage, getattr(event, "usage", None)
                        )
                        usage = self._merge_stream_usage(
                            usage, getattr(delta, "usage", None)
                        )
                        reason = getattr(delta, "stop_reason", None)
                        if reason:
                            finish_reason = self._normalize_finish_reason(reason)
            except Exception as e:
                raise RuntimeError(f"Anthropic stream iteration failed: {e}") from e
            if usage is not None:
                self._track_usage(LLMResponse(usage=usage))
            yield LLMChunk(
                finish_reason=finish_reason,
                usage=usage,
                request_id=request_id,
            )

        return Result.ok(_chunks())

    def _format_messages(
        self, messages: List[ChatMessage]
    ) -> Result[Tuple[Optional[str], List[Dict[str, Any]]], Dict[str, Any]]:
        """Format text/image messages for the Anthropic Messages API."""

        system_prompt: Optional[str] = None
        conversation: List[Dict[str, Any]] = []
        for message in messages:
            formatted_content = self._format_content(message.content)
            if formatted_content.is_err():
                return Result.err(formatted_content.unwrap_err())
            content = formatted_content.unwrap()
            if message.role == ChatRole.SYSTEM:
                if not isinstance(content, str):
                    return Result.err(
                        {
                            "errorType": "LLM_UNSUPPORTED_CONTENT",
                            "message": "Anthropic system prompts must be text.",
                        }
                    )
                system_prompt = content
            elif message.role == ChatRole.TOOL:
                if not isinstance(content, str):
                    return Result.err(
                        {
                            "errorType": "LLM_UNSUPPORTED_CONTENT",
                            "message": "Anthropic tool results must be text.",
                        }
                    )
                conversation.append(
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "tool_result",
                                "tool_use_id": message.tool_call_id,
                                "content": content,
                            }
                        ],
                    }
                )
            elif message.role == ChatRole.ASSISTANT and message.tool_calls:
                content_blocks: List[Dict[str, Any]] = []
                if isinstance(content, str):
                    if content:
                        content_blocks.append({"type": "text", "text": content})
                else:
                    content_blocks.extend(content)
                for tool_call in message.tool_calls:
                    content_blocks.append(
                        {
                            "type": "tool_use",
                            "id": tool_call.id,
                            "name": tool_call.name,
                            "input": tool_call.arguments,
                        }
                    )
                conversation.append({"role": "assistant", "content": content_blocks})
            else:
                conversation.append({"role": message.role.value, "content": content})
        return Result.ok((system_prompt, conversation))

    @staticmethod
    def _format_content(content: ChatContent) -> Result[Any, Dict[str, Any]]:
        if isinstance(content, str):
            return Result.ok(content or "")
        formatted: List[Dict[str, Any]] = []
        for part in content:
            if isinstance(part, str):
                formatted.append({"type": "text", "text": part})
            elif isinstance(part, ImageContent):
                if not part.source.startswith("data:"):
                    return Result.err(
                        {
                            "errorType": "LLM_UNSUPPORTED_CONTENT",
                            "message": (
                                "Anthropic image input requires a base64 data URI."
                            ),
                        }
                    )
                header, separator, data = part.source.partition(",")
                if not separator or ";base64" not in header:
                    return Result.err(
                        {
                            "errorType": "LLM_CONTENT_INVALID",
                            "message": "Anthropic image data URI is malformed.",
                        }
                    )
                mime_type = header[5:].split(";", 1)[0]
                formatted.append(
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": mime_type,
                            "data": data,
                        },
                    }
                )
            else:
                return Result.err(
                    {
                        "errorType": "LLM_CONTENT_INVALID",
                        "message": "Unsupported chat content part.",
                    }
                )
        return Result.ok(formatted)

    def _format_tool(self, tool: ToolDefinition) -> Dict[str, Any]:
        return {
            "name": tool.name,
            "description": tool.description,
            "input_schema": tool.parameters,
        }

    def _parse_response(self, response: Any) -> LLMResponse:
        content_text = ""
        tool_calls = []

        for block in response.content:
            if block.type == "text":
                content_text += block.text
            elif block.type == "tool_use":
                if not isinstance(block.input, dict):
                    raise ProviderResponseError(
                        "provider tool arguments must be an object"
                    )
                tool_calls.append(
                    ToolCall(
                        id=block.id,
                        name=block.name,
                        arguments=block.input,
                    )
                )

        usage = self._parse_completion_usage(getattr(response, "usage", None))

        finish_reason = self._normalize_finish_reason(response.stop_reason or "")

        return LLMResponse(
            content=content_text or None,
            tool_calls=tool_calls,
            usage=usage,
            model=response.model,
            finish_reason=finish_reason,
            raw_response=response,
            request_id=self._bounded_request_id(getattr(response, "id", None)),
        )

    @staticmethod
    def _normalize_finish_reason(reason: str) -> str:
        if reason == "end_turn":
            return "stop"
        if reason == "tool_use":
            return "tool_calls"
        return reason
