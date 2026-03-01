"""Tests for LLM types."""

import pytest
from maple.llm.types import (
    ChatRole, ChatMessage, ToolDefinition, ToolCall, ToolResult,
    TokenUsage, LLMResponse, LLMChunk, LLMConfig,
)


class TestChatRole:
    def test_role_values(self):
        assert ChatRole.SYSTEM.value == "system"
        assert ChatRole.USER.value == "user"
        assert ChatRole.ASSISTANT.value == "assistant"
        assert ChatRole.TOOL.value == "tool"

    def test_role_from_value(self):
        assert ChatRole("system") == ChatRole.SYSTEM
        assert ChatRole("assistant") == ChatRole.ASSISTANT


class TestChatMessage:
    def test_basic_message(self):
        msg = ChatMessage(role=ChatRole.USER, content="hello")
        assert msg.role == ChatRole.USER
        assert msg.content == "hello"
        assert msg.name is None
        assert msg.tool_call_id is None
        assert msg.tool_calls is None

    def test_system_message(self):
        msg = ChatMessage(role=ChatRole.SYSTEM, content="You are helpful.")
        assert msg.role == ChatRole.SYSTEM

    def test_tool_message(self):
        msg = ChatMessage(
            role=ChatRole.TOOL,
            content='{"result": 42}',
            tool_call_id="tc_123",
            name="calculator",
        )
        assert msg.tool_call_id == "tc_123"
        assert msg.name == "calculator"

    def test_assistant_with_tool_calls(self):
        tc = ToolCall(id="tc_1", name="search", arguments={"q": "test"})
        msg = ChatMessage(
            role=ChatRole.ASSISTANT,
            content="Let me search.",
            tool_calls=[tc],
        )
        assert len(msg.tool_calls) == 1
        assert msg.tool_calls[0].name == "search"


class TestToolDefinition:
    def test_creation(self):
        td = ToolDefinition(
            name="calc",
            description="Calculator",
            parameters={"type": "object", "properties": {"x": {"type": "number"}}},
        )
        assert td.name == "calc"
        assert td.description == "Calculator"
        assert "properties" in td.parameters


class TestToolCall:
    def test_creation(self):
        tc = ToolCall(id="tc_1", name="search", arguments={"query": "test"})
        assert tc.id == "tc_1"
        assert tc.name == "search"
        assert tc.arguments["query"] == "test"


class TestToolResult:
    def test_success(self):
        tr = ToolResult(tool_call_id="tc_1", content='{"answer": 42}')
        assert not tr.is_error
        assert tr.tool_call_id == "tc_1"

    def test_error(self):
        tr = ToolResult(tool_call_id="tc_1", content="error occurred", is_error=True)
        assert tr.is_error


class TestTokenUsage:
    def test_defaults(self):
        usage = TokenUsage()
        assert usage.prompt_tokens == 0
        assert usage.completion_tokens == 0
        assert usage.total_tokens == 0

    def test_with_values(self):
        usage = TokenUsage(prompt_tokens=100, completion_tokens=50, total_tokens=150)
        assert usage.total_tokens == 150


class TestLLMResponse:
    def test_defaults(self):
        resp = LLMResponse()
        assert resp.content is None
        assert resp.tool_calls == []
        assert resp.usage is None
        assert resp.model == ""
        assert resp.finish_reason == ""

    def test_with_content(self):
        resp = LLMResponse(
            content="Hello!",
            model="gpt-4",
            finish_reason="stop",
            usage=TokenUsage(prompt_tokens=10, completion_tokens=5, total_tokens=15),
        )
        assert resp.content == "Hello!"
        assert resp.usage.total_tokens == 15

    def test_with_tool_calls(self):
        tc = ToolCall(id="tc_1", name="calc", arguments={"x": 1})
        resp = LLMResponse(tool_calls=[tc], finish_reason="tool_calls")
        assert len(resp.tool_calls) == 1


class TestLLMChunk:
    def test_defaults(self):
        chunk = LLMChunk()
        assert chunk.content == ""
        assert chunk.tool_call_delta is None
        assert chunk.finish_reason is None

    def test_content_chunk(self):
        chunk = LLMChunk(content="Hello")
        assert chunk.content == "Hello"

    def test_finish_chunk(self):
        chunk = LLMChunk(finish_reason="stop")
        assert chunk.finish_reason == "stop"


class TestLLMConfig:
    def test_minimal(self):
        config = LLMConfig(provider="openai", model="gpt-4")
        assert config.provider == "openai"
        assert config.model == "gpt-4"
        assert config.temperature == 0.7
        assert config.max_tokens == 4096
        assert config.timeout == 120.0

    def test_full_config(self):
        config = LLMConfig(
            provider="anthropic",
            model="claude-3-opus",
            api_key="sk-test",
            api_base="https://api.example.com",
            temperature=0.3,
            max_tokens=2048,
            system_prompt="Be helpful",
            timeout=60.0,
            extra={"top_p": 0.9},
        )
        assert config.api_key == "sk-test"
        assert config.extra["top_p"] == 0.9
