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

"""Anthropic Claude LLM provider."""

import logging
from typing import Any, AsyncIterator, Dict, List, Optional

from ..core.result import Result
from .provider import LLMProvider
from .types import (
    ChatMessage, ChatRole, LLMChunk, LLMConfig, LLMResponse,
    ToolCall, ToolDefinition, TokenUsage,
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
            client_kwargs = {}
            if config.api_key:
                client_kwargs['api_key'] = config.api_key
            if config.api_base:
                client_kwargs['base_url'] = config.api_base
            if config.timeout:
                client_kwargs['timeout'] = config.timeout
            self.client = anthropic.Anthropic(**client_kwargs)
            async_client_type = getattr(anthropic, 'AsyncAnthropic', None)
            if async_client_type is not None:
                self.async_client = async_client_type(**client_kwargs)
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
            return Result.err({
                'errorType': 'PROVIDER_NOT_AVAILABLE',
                'message': (
                    'anthropic library not installed. Install with: '
                    'pip install anthropic'
                )
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
                'temperature': (
                    temperature
                    if temperature is not None
                    else self.config.temperature
                ),
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
                    'content': msg.content or '',
                })

        kwargs: Dict[str, Any] = {
            'model': self.config.model,
            'messages': conversation,
            'max_tokens': max_tokens or self.config.max_tokens,
            'temperature': (
                temperature if temperature is not None else self.config.temperature
            ),
            'stream': True,
        }
        if system_prompt:
            kwargs['system'] = system_prompt
        if tools:
            kwargs['tools'] = [self._format_tool(t) for t in tools]

        try:
            response_stream = await self.async_client.messages.create(**kwargs)
        except Exception as e:
            return Result.err({
                'errorType': 'LLM_STREAM_ERROR',
                'message': f'Anthropic streaming failed: {str(e)}'
            })

        async def _chunks() -> AsyncIterator[LLMChunk]:
            finish_reason = None
            try:
                async for event in response_stream:
                    event_type = getattr(event, 'type', '')
                    if event_type == 'content_block_start':
                        block = getattr(event, 'content_block', None)
                        if getattr(block, 'type', None) == 'tool_use':
                            yield LLMChunk(tool_call_delta={
                                'id': getattr(block, 'id', None),
                                'name': getattr(block, 'name', None),
                                'arguments': {},
                            })
                    elif event_type == 'content_block_delta':
                        delta = getattr(event, 'delta', None)
                        delta_type = getattr(delta, 'type', '')
                        if delta_type == 'text_delta':
                            for text in self._bounded_text_chunks(
                                getattr(delta, 'text', '') or ''
                            ):
                                yield LLMChunk(content=text)
                        elif delta_type == 'input_json_delta':
                            yield LLMChunk(tool_call_delta={
                                'arguments': getattr(delta, 'partial_json', '') or '',
                            })
                    elif event_type == 'message_delta':
                        delta = getattr(event, 'delta', None)
                        reason = getattr(delta, 'stop_reason', None)
                        if reason:
                            finish_reason = self._normalize_finish_reason(reason)
            except Exception as e:
                raise RuntimeError(f'Anthropic stream iteration failed: {e}') from e
            yield LLMChunk(finish_reason=finish_reason)

        return Result.ok(_chunks())

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

        finish_reason = self._normalize_finish_reason(response.stop_reason or "")

        return LLMResponse(
            content=content_text or None,
            tool_calls=tool_calls,
            usage=usage,
            model=response.model,
            finish_reason=finish_reason,
            raw_response=response,
        )

    @staticmethod
    def _normalize_finish_reason(reason: str) -> str:
        if reason == "end_turn":
            return "stop"
        if reason == "tool_use":
            return "tool_calls"
        return reason
