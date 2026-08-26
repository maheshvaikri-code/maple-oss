# Copyright (C) 2025 Mahesh Vaijainthymala Krishnamoorthy (Mahesh Vaikri)
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

"""OpenAI-compatible LLM provider."""

import json
import logging
from typing import Any, AsyncIterator, Dict, List, Optional, cast

from ..core.result import Result
from .provider import LLMProvider
from .types import (
    ChatMessage,
    LLMChunk,
    LLMConfig,
    LLMResponse,
    TokenUsage,
    ToolCall,
    ToolDefinition,
)

logger = logging.getLogger(__name__)


class OpenAIProvider(LLMProvider):
    """
    OpenAI and OpenAI-compatible API provider.
    Works with OpenAI, Azure OpenAI, Together, vLLM, Ollama, etc.
    """

    def __init__(self, config: LLMConfig):
        super().__init__(config)
        self.client = None
        self.async_client = None
        try:
            import openai

            client_kwargs: Dict[str, Any] = {}
            if config.api_key:
                client_kwargs["api_key"] = config.api_key
            if config.api_base:
                client_kwargs["base_url"] = config.api_base
            if config.timeout:
                client_kwargs["timeout"] = config.timeout
            self.client = cast(Any, openai.OpenAI)(**client_kwargs)
            self.async_client = cast(Any, openai.AsyncOpenAI)(**client_kwargs)
        except ImportError:
            logger.warning(
                "openai library not installed. Install with: " "pip install openai"
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
                        "openai library not installed. Install with: "
                        "pip install openai"
                    ),
                }
            )
        try:
            kwargs: Dict[str, Any] = {
                "model": self.config.model,
                "messages": [self._format_message(m) for m in messages],
                "temperature": (
                    temperature if temperature is not None else self.config.temperature
                ),
                "max_tokens": max_tokens or self.config.max_tokens,
            }
            if stop:
                kwargs["stop"] = stop
            if tools:
                kwargs["tools"] = [self._format_tool(t) for t in tools]
                kwargs["tool_choice"] = "auto"

            response = cast(Any, self.client).chat.completions.create(**kwargs)
            llm_response = self._parse_response(response)
            self._track_usage(llm_response)
            return Result.ok(llm_response)
        except Exception as e:
            return Result.err(
                {
                    "errorType": "LLM_COMPLETION_ERROR",
                    "message": f"OpenAI completion failed: {str(e)}",
                }
            )

    async def stream(
        self,
        messages: List[ChatMessage],
        tools: Optional[List[ToolDefinition]] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> Result[AsyncIterator[LLMChunk], Dict[str, Any]]:
        """Return native OpenAI-compatible chat completion deltas."""
        if not self.async_client:
            return await super().stream(
                messages,
                tools=tools,
                temperature=temperature,
                max_tokens=max_tokens,
            )

        kwargs: Dict[str, Any] = {
            "model": self.config.model,
            "messages": [self._format_message(m) for m in messages],
            "temperature": (
                temperature if temperature is not None else self.config.temperature
            ),
            "max_tokens": max_tokens or self.config.max_tokens,
            "stream": True,
        }
        if tools:
            kwargs["tools"] = [self._format_tool(t) for t in tools]
            kwargs["tool_choice"] = "auto"
        if self.config.extra.get("include_stream_usage") is True:
            kwargs["stream_options"] = {"include_usage": True}

        try:
            response_stream = await cast(
                Any, self.async_client
            ).chat.completions.create(**kwargs)
        except Exception as e:
            return Result.err(
                {
                    "errorType": "LLM_STREAM_ERROR",
                    "message": f"OpenAI streaming failed: {str(e)}",
                }
            )

        async def _chunks() -> AsyncIterator[LLMChunk]:
            finish_reason = None
            request_id = None
            usage = None
            try:
                async for chunk in response_stream:
                    request_id = (
                        self._bounded_request_id(getattr(chunk, "id", None))
                        or request_id
                    )
                    usage = self._merge_stream_usage(
                        usage, getattr(chunk, "usage", None)
                    )
                    choices = getattr(chunk, "choices", None) or []
                    if not choices:
                        continue
                    choice = choices[0]
                    delta = getattr(choice, "delta", None)
                    if delta is not None:
                        content = getattr(delta, "content", None) or ""
                        for text in self._bounded_text_chunks(content):
                            yield LLMChunk(content=text)
                        for tool_call in getattr(delta, "tool_calls", None) or []:
                            function = getattr(tool_call, "function", None)
                            tool_call_delta = {
                                "id": getattr(tool_call, "id", None),
                                "name": getattr(function, "name", None),
                                "arguments": getattr(function, "arguments", None),
                            }
                            tool_call_index = getattr(tool_call, "index", None)
                            if tool_call_index is not None:
                                tool_call_delta["index"] = tool_call_index
                            yield LLMChunk(tool_call_delta=tool_call_delta)
                    reason = getattr(choice, "finish_reason", None)
                    if reason:
                        finish_reason = reason
            except Exception as e:
                raise RuntimeError(f"OpenAI stream iteration failed: {e}") from e
            if usage is not None:
                self._track_usage(LLMResponse(usage=usage))
            yield LLMChunk(
                finish_reason=finish_reason,
                usage=usage,
                request_id=request_id,
            )

        return Result.ok(_chunks())

    def _format_message(self, msg: ChatMessage) -> Dict[str, Any]:
        d: Dict[str, Any] = {"role": msg.role.value, "content": msg.content or ""}
        if msg.name:
            d["name"] = msg.name
        if msg.tool_call_id:
            d["tool_call_id"] = msg.tool_call_id
        if msg.tool_calls:
            d["tool_calls"] = [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {
                        "name": tc.name,
                        "arguments": json.dumps(tc.arguments),
                    },
                }
                for tc in msg.tool_calls
            ]
        return d

    def _format_tool(self, tool: ToolDefinition) -> Dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": tool.name,
                "description": tool.description,
                "parameters": tool.parameters,
            },
        }

    def _parse_response(self, response: Any) -> LLMResponse:
        choice = response.choices[0]
        msg = choice.message
        tool_calls = []
        if msg.tool_calls:
            for tc in msg.tool_calls:
                try:
                    args = json.loads(tc.function.arguments)
                except (json.JSONDecodeError, TypeError):
                    args = {}
                tool_calls.append(
                    ToolCall(
                        id=tc.id,
                        name=tc.function.name,
                        arguments=args,
                    )
                )
        usage = None
        if response.usage:
            usage = TokenUsage(
                prompt_tokens=response.usage.prompt_tokens,
                completion_tokens=response.usage.completion_tokens,
                total_tokens=response.usage.total_tokens,
            )
        return LLMResponse(
            content=msg.content,
            tool_calls=tool_calls,
            usage=usage,
            model=response.model,
            finish_reason=choice.finish_reason,
            raw_response=response,
            request_id=self._bounded_request_id(getattr(response, "id", None)),
        )
