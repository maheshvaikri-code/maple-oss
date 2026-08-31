"""Tests for the provider-agnostic completion-backed stream contract."""

import asyncio

from maple.core.result import Result
from maple.llm.provider import LLMProvider
from maple.llm.types import (
    ChatMessage,
    ChatRole,
    LLMChunk,
    LLMConfig,
    LLMResponse,
    TokenUsage,
    ToolCall,
)


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


class AsyncEvents:
    def __init__(self, events):
        self.events = events

    def __aiter__(self):
        return self

    async def __anext__(self):
        if not self.events:
            raise StopAsyncIteration
        return self.events.pop(0)


class ChunkProvider(LLMProvider):
    def __init__(self, chunks):
        super().__init__(LLMConfig(provider="test", model="test-model"))
        self.chunks = chunks

    def complete(
        self, messages, tools=None, temperature=None, max_tokens=None, stop=None
    ):
        return Result.err({"errorType": "UNUSED", "message": "stream only"})

    async def stream(
        self, messages, tools=None, temperature=None, max_tokens=None, stop=None
    ):
        return Result.ok(AsyncEvents(list(self.chunks)))


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


def test_complete_from_stream_reconstructs_text_tool_arguments_and_trailers():
    provider = ChunkProvider(
        [
            LLMChunk(content="hel"),
            LLMChunk(content="lo"),
            LLMChunk(
                tool_call_delta={
                    "index": 0,
                    "id": "call-1",
                    "name": "lookup",
                    "arguments": '{"q"',
                }
            ),
            LLMChunk(tool_call_delta={"arguments": ':"MAPLE"}'}),
            LLMChunk(
                finish_reason="tool_calls",
                usage=TokenUsage(
                    prompt_tokens=12, completion_tokens=7, total_tokens=19
                ),
                request_id="stream-1",
            ),
        ]
    )
    seen = []

    result = asyncio.run(
        provider.complete_from_stream(
            [ChatMessage(role=ChatRole.USER, content="hi")],
            on_chunk=seen.append,
        )
    )

    assert result.is_ok()
    response = result.unwrap()
    assert response.content == "hello"
    assert response.tool_calls == [
        ToolCall(id="call-1", name="lookup", arguments={"q": "MAPLE"})
    ]
    assert response.finish_reason == "tool_calls"
    assert response.usage == TokenUsage(
        prompt_tokens=12, completion_tokens=7, total_tokens=19
    )
    assert response.request_id == "stream-1"
    assert len(seen) == 5


def test_complete_from_stream_fails_closed_for_unbounded_content():
    provider = ChunkProvider([LLMChunk(content="x" * (1_048_576 + 1))])

    result = asyncio.run(
        provider.complete_from_stream([ChatMessage(role=ChatRole.USER, content="hi")])
    )

    assert result.is_err()
    assert result.unwrap_err()["errorType"] == "LLM_STREAM_CHUNK_TOO_LARGE"


def test_complete_from_stream_starts_new_id_without_an_explicit_index():
    provider = ChunkProvider(
        [
            LLMChunk(
                tool_call_delta={
                    "id": "call-1",
                    "name": "first",
                    "arguments": {},
                }
            ),
            LLMChunk(
                tool_call_delta={
                    "id": "call-2",
                    "name": "second",
                    "arguments": {},
                }
            ),
        ]
    )

    result = asyncio.run(
        provider.complete_from_stream([ChatMessage(role=ChatRole.USER, content="hi")])
    )

    assert result.is_ok()
    assert [(call.id, call.name) for call in result.unwrap().tool_calls] == [
        ("call-1", "first"),
        ("call-2", "second"),
    ]


async def _collect(iterator):
    return [chunk async for chunk in iterator]
