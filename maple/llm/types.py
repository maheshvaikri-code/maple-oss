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

"""LLM types for MAPLE autonomy layer."""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from enum import Enum


class ChatRole(Enum):
    """Role of a message in a conversation."""
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"


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
    content: str
    name: Optional[str] = None
    tool_call_id: Optional[str] = None
    tool_calls: Optional[List[ToolCall]] = None


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


@dataclass
class LLMChunk:
    """A single chunk from a streaming LLM response."""
    content: str = ""
    tool_call_delta: Optional[Dict[str, Any]] = None
    finish_reason: Optional[str] = None


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
