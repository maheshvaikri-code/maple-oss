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

"""Anthropic Claude LLM provider."""

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


class AnthropicProvider(LLMProvider):
    """Anthropic Claude API provider."""

    def __init__(self, config: LLMConfig):
        super().__init__(config)
        self.client = None
        try:
            import anthropic
            client_kwargs = {}
            if config.api_key:
                client_kwargs['api_key'] = config.api_key
            if config.api_base:
                client_kwargs['base_url'] = config.api_base
            if config.timeout:
                client_kwargs['timeout'] = config.timeout
            self.client = anthropic.Anthropic(**client_kwargs)
        except ImportError:
            logger.warning("anthropic library not installed. Install with: pip install anthropic")

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
                'message': 'anthropic library not installed. Install with: pip install anthropic'
            })
        try:
            # Anthropic uses system as a separate parameter
            system_prompt = None
            conversation = []
            for msg in messages:
                if msg.role == ChatRole.SYSTEM:
                    system_prompt = msg.content
                elif msg.role == ChatRole.TOOL:
                    conversation.append({
                        'role': 'user',
                        'content': [{
                            'type': 'tool_result',
                            'tool_use_id': msg.tool_call_id,
                            'content': msg.content,
                        }]
                    })
                elif msg.role == ChatRole.ASSISTANT and msg.tool_calls:
                    content = []
                    if msg.content:
                        content.append({'type': 'text', 'text': msg.content})
                    for tc in msg.tool_calls:
                        content.append({
                            'type': 'tool_use',
                            'id': tc.id,
                            'name': tc.name,
                            'input': tc.arguments,
                        })
                    conversation.append({'role': 'assistant', 'content': content})
                else:
                    conversation.append({
                        'role': msg.role.value,
                        'content': msg.content or "",
                    })

            kwargs: Dict[str, Any] = {
                'model': self.config.model,
                'messages': conversation,
                'max_tokens': max_tokens or self.config.max_tokens,
                'temperature': temperature if temperature is not None else self.config.temperature,
            }
            if system_prompt:
                kwargs['system'] = system_prompt
            if stop:
                kwargs['stop_sequences'] = stop
            if tools:
                kwargs['tools'] = [self._format_tool(t) for t in tools]

            response = self.client.messages.create(**kwargs)
            llm_response = self._parse_response(response)
            self._track_usage(llm_response)
            return Result.ok(llm_response)
        except Exception as e:
            return Result.err({
                'errorType': 'LLM_COMPLETION_ERROR',
                'message': f'Anthropic completion failed: {str(e)}'
            })

    def _format_tool(self, tool: ToolDefinition) -> Dict[str, Any]:
        return {
            'name': tool.name,
            'description': tool.description,
            'input_schema': tool.parameters,
        }

    def _parse_response(self, response) -> LLMResponse:
        content_text = ""
        tool_calls = []

        for block in response.content:
            if block.type == 'text':
                content_text += block.text
            elif block.type == 'tool_use':
                tool_calls.append(ToolCall(
                    id=block.id,
                    name=block.name,
                    arguments=block.input if isinstance(block.input, dict) else {},
                ))

        usage = None
        if response.usage:
            usage = TokenUsage(
                prompt_tokens=response.usage.input_tokens,
                completion_tokens=response.usage.output_tokens,
                total_tokens=response.usage.input_tokens + response.usage.output_tokens,
            )

        finish_reason = response.stop_reason or ""
        if finish_reason == "end_turn":
            finish_reason = "stop"
        elif finish_reason == "tool_use":
            finish_reason = "tool_calls"

        return LLMResponse(
            content=content_text or None,
            tool_calls=tool_calls,
            usage=usage,
            model=response.model,
            finish_reason=finish_reason,
            raw_response=response,
        )
