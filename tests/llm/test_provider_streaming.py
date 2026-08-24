"""Tests for the provider-agnostic completion-backed stream contract."""

import asyncio

from maple.core.result import Result
from maple.llm.provider import LLMProvider
from maple.llm.types import ChatMessage, ChatRole, LLMConfig, LLMResponse, ToolCall


class StreamingProvider(LLMProvider):
    def __init__(self, response):
        super().__init__(LLMConfig(provider="test", model="test-model"))
        self.response = response

    def complete(
        self, messages, tools=None, temperature=None, max_tokens=None, stop=None
    ):
        return Result.ok(self.response)


class FailingProvider(LLMProvider):
    def __init__(self):
        super().__init__(LLMConfig(provider="test", model="test-model"))

    def complete(
        self, messages, tools=None, temperature=None, max_tokens=None, stop=None
    ):
        return Result.err(
            {"errorType": "MODEL_DOWN", "message": "provider unavailable"}
        )


def test_stream_fallback_yields_bounded_text_tool_and_finish_chunks():
    provider = StreamingProvider(
        LLMResponse(
            content="x" * 513,
            tool_calls=[ToolCall(id="call-1", name="lookup", arguments={"q": "MAPLE"})],
            finish_reason="tool_calls",
        )
    )

    result = asyncio.run(
        provider.stream([ChatMessage(role=ChatRole.USER, content="hi")])
    )

    assert result.is_ok()
    chunks = asyncio.run(_collect(result.unwrap()))
    text_chunks = [chunk for chunk in chunks if chunk.content]
    assert [len(chunk.content) for chunk in text_chunks] == [256, 256, 1]
    assert chunks[-2].tool_call_delta == {
        "id": "call-1",
        "name": "lookup",
        "arguments": {"q": "MAPLE"},
    }
    assert chunks[-1].finish_reason == "tool_calls"


def test_stream_propagates_completion_error_as_result_data():
    result = asyncio.run(
        FailingProvider().stream([ChatMessage(role=ChatRole.USER, content="hi")])
    )

    assert result.is_err()
    assert result.unwrap_err()["errorType"] == "MODEL_DOWN"


async def _collect(iterator):
    return [chunk async for chunk in iterator]
