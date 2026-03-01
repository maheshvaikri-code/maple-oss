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

"""OpenAI-compatible LLM provider."""

import json
import logging
from typing import Any, Dict, List, Optional

from ..core.result import Result
from .provider import LLMProvider
from .types import (
    ChatMessage, ChatRole, LLMConfig, LLMResponse,
    ToolCall, ToolDefinition, TokenUsage,
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
            client_kwargs = {}
            if config.api_key:
                client_kwargs['api_key'] = config.api_key
            if config.api_base:
                client_kwargs['base_url'] = config.api_base
            if config.timeout:
                client_kwargs['timeout'] = config.timeout
            self.client = openai.OpenAI(**client_kwargs)
            self.async_client = openai.AsyncOpenAI(**client_kwargs)
        except ImportError:
            logger.warning("openai library not installed. Install with: pip install openai")

    def complete(
        self,
        messages: List[ChatMessage],
        tools: Optional[List[ToolDefinition]] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        stop: Optional[List[str]] = None,
    ) -> Result[LLMResponse, Dict[str, Any]]:
        if not self.client:
            return Result.err({
                'errorType': 'PROVIDER_NOT_AVAILABLE',
                'message': 'openai library not installed. Install with: pip install openai'
            })
        try:
            kwargs = {
                'model': self.config.model,
                'messages': [self._format_message(m) for m in messages],
                'temperature': temperature if temperature is not None else self.config.temperature,
                'max_tokens': max_tokens or self.config.max_tokens,
            }
            if stop:
                kwargs['stop'] = stop
            if tools:
                kwargs['tools'] = [self._format_tool(t) for t in tools]
                kwargs['tool_choice'] = 'auto'

            response = self.client.chat.completions.create(**kwargs)
            llm_response = self._parse_response(response)
            self._track_usage(llm_response)
            return Result.ok(llm_response)
        except Exception as e:
            return Result.err({
                'errorType': 'LLM_COMPLETION_ERROR',
                'message': f'OpenAI completion failed: {str(e)}'
            })

    def _format_message(self, msg: ChatMessage) -> Dict[str, Any]:
        d: Dict[str, Any] = {'role': msg.role.value, 'content': msg.content or ""}
        if msg.name:
            d['name'] = msg.name
        if msg.tool_call_id:
            d['tool_call_id'] = msg.tool_call_id
        if msg.tool_calls:
            d['tool_calls'] = [
                {
                    'id': tc.id,
                    'type': 'function',
                    'function': {
                        'name': tc.name,
                        'arguments': json.dumps(tc.arguments)
                    }
                }
                for tc in msg.tool_calls
            ]
        return d

    def _format_tool(self, tool: ToolDefinition) -> Dict[str, Any]:
        return {
            'type': 'function',
            'function': {
                'name': tool.name,
                'description': tool.description,
                'parameters': tool.parameters,
            }
        }

    def _parse_response(self, response) -> LLMResponse:
        choice = response.choices[0]
        msg = choice.message
        tool_calls = []
        if msg.tool_calls:
            for tc in msg.tool_calls:
                try:
                    args = json.loads(tc.function.arguments)
                except (json.JSONDecodeError, TypeError):
                    args = {}
                tool_calls.append(ToolCall(
                    id=tc.id,
                    name=tc.function.name,
                    arguments=args,
                ))
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
        )
