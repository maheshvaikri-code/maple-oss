# Copyright (C) 2025 Mahesh Vaijainthymala Krishnamoorthy (Mahesh Vaikri)
#
# This file is part of MAPLE - Multi Agent Protocol Language Engine.
#
# MAPLE - Multi Agent Protocol Language Engine is free software: you can
# redistribute it and/or modify it under the terms of the GNU Affero General
# Public License as published by the Free Software Foundation, either version
# 3 of the License, or (at your option) any later version.
# MAPLE - Multi Agent Protocol Language Engine is distributed in the hope that
# it will be useful, but WITHOUT ANY WARRANTY; without even the implied warranty
# of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU Affero
# General Public License for more details. You should have received a copy of
# the GNU Affero General Public License along with MAPLE - Multi Agent Protocol
# Language Engine. If not, see <https://www.gnu.org/licenses/>.

"""Abstract LLM provider base class."""

from abc import ABC, abstractmethod
from typing import Any, AsyncIterator, Dict, Iterator, List, Optional

from ..core.result import Result
from .types import ChatMessage, LLMChunk, LLMConfig, LLMResponse, ToolDefinition


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
    ) -> Result['LLMResponse', Dict[str, Any]]:
        """Send a completion request to the LLM."""
        ...

    async def complete_async(
        self,
        messages: List[ChatMessage],
        tools: Optional[List[ToolDefinition]] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        stop: Optional[List[str]] = None,
    ) -> Result['LLMResponse', Dict[str, Any]]:
        """Async version of complete(). Default delegates to sync."""
        return self.complete(messages, tools, temperature, max_tokens, stop)

    async def stream(
        self,
        messages: List[ChatMessage],
        tools: Optional[List[ToolDefinition]] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> Result[AsyncIterator['LLMChunk'], Dict[str, Any]]:
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
            yield LLMChunk(finish_reason=response.finish_reason or None)

        return Result.ok(_chunks())

    @staticmethod
    def _bounded_text_chunks(content: str) -> Iterator[str]:
        """Split provider text into bounded chunks for the shared contract."""
        for offset in range(0, len(content), 256):
            yield content[offset : offset + 256]

    def count_tokens(self, text: str) -> int:
        """Estimate token count (provider-specific override recommended)."""
        return len(text) // 4

    def get_usage_stats(self) -> Dict[str, Any]:
        """Get cumulative usage statistics."""
        return {
            'total_prompt_tokens': self._total_prompt_tokens,
            'total_completion_tokens': self._total_completion_tokens,
            'total_cost_usd': self._total_cost,
            'provider': self.config.provider,
            'model': self.config.model,
        }

    def _track_usage(self, response: LLMResponse) -> None:
        """Track token usage from a response."""
        if response.usage:
            self._total_prompt_tokens += response.usage.prompt_tokens
            self._total_completion_tokens += response.usage.completion_tokens
