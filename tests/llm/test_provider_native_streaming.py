"""Tests for provider-native streaming adapters without network access."""

import asyncio
from types import SimpleNamespace

from maple.core.result import Result
from maple.llm.anthropic_provider import AnthropicProvider
from maple.llm.openai_provider import OpenAIProvider
from maple.llm.provider import LLMProvider
from maple.llm.types import ChatMessage, ChatRole, LLMConfig, ToolDefinition


class AsyncEvents:
    def __init__(self, events):
        self.events = events

    def __aiter__(self):
        return self

    async def __anext__(self):
        if not self.events:
            raise StopAsyncIteration
        return self.events.pop(0)


class OpenAICompletions:
    def __init__(self, events):
        self.events = events
        self.kwargs = None

    async def create(self, **kwargs):
        self.kwargs = kwargs
        return AsyncEvents(list(self.events))


class AnthropicMessages:
    def __init__(self, events):
        self.events = events
        self.kwargs = None

    async def create(self, **kwargs):
        self.kwargs = kwargs
        return AsyncEvents(list(self.events))


def _provider_without_constructor(provider_type, config):
    provider = object.__new__(provider_type)
    LLMProvider.__init__(provider, config)
    return provider


def test_openai_native_stream_maps_text_tool_and_finish_deltas():
    events = [
        SimpleNamespace(
            choices=[
                SimpleNamespace(
                    delta=SimpleNamespace(content="h" * 513, tool_calls=None),
                    finish_reason=None,
                )
            ]
        ),
        SimpleNamespace(
            choices=[
                SimpleNamespace(
                    delta=SimpleNamespace(
                        content=None,
                        tool_calls=[
                            SimpleNamespace(
                                id="call-1",
                                function=SimpleNamespace(
                                    name="lookup", arguments='{"q"'
                                ),
                            )
                        ],
                    ),
                    finish_reason=None,
                )
            ]
        ),
        SimpleNamespace(
            choices=[
                SimpleNamespace(
                    delta=SimpleNamespace(content=" world", tool_calls=None),
                    finish_reason="tool_calls",
                )
            ]
        ),
        SimpleNamespace(
            id="chatcmpl-stream-1",
            choices=[],
            usage=SimpleNamespace(
                prompt_tokens=12,
                completion_tokens=7,
                total_tokens=19,
            ),
        ),
    ]
    client = OpenAICompletions(events)
    provider = _provider_without_constructor(
        OpenAIProvider,
        LLMConfig(
            provider="openai",
            model="gpt-test",
            extra={"include_stream_usage": True},
        ),
    )
    provider.async_client = SimpleNamespace(chat=SimpleNamespace(completions=client))

    result = asyncio.run(
        provider.stream(
            [ChatMessage(role=ChatRole.USER, content="hi")],
            tools=[ToolDefinition("lookup", "Find data", {"type": "object"})],
        )
    )

    assert result.is_ok()
    chunks = asyncio.run(_collect(result.unwrap()))
    assert "".join(chunk.content for chunk in chunks) == "h" * 513 + " world"
    assert [len(chunk.content) for chunk in chunks if chunk.content] == [256, 256, 1, 6]
    tool_chunk = next(chunk for chunk in chunks if chunk.tool_call_delta)
    assert tool_chunk.tool_call_delta == {
        "id": "call-1",
        "name": "lookup",
        "arguments": '{"q"',
    }
    assert chunks[-1].finish_reason == "tool_calls"
    assert chunks[-1].usage.prompt_tokens == 12
    assert chunks[-1].usage.completion_tokens == 7
    assert chunks[-1].usage.total_tokens == 19
    assert chunks[-1].request_id == "chatcmpl-stream-1"
    assert provider.get_usage_stats()["total_prompt_tokens"] == 12
    assert provider.get_usage_stats()["total_completion_tokens"] == 7
    assert client.kwargs["stream"] is True
    assert client.kwargs["stream_options"] == {"include_usage": True}
    assert client.kwargs["tools"][0]["function"]["name"] == "lookup"


def test_anthropic_native_stream_maps_text_tool_json_and_finish_deltas():
    events = [
        SimpleNamespace(
            type="message_start",
            message=SimpleNamespace(
                id="msg-stream-1",
                usage=SimpleNamespace(input_tokens=9),
            ),
        ),
        SimpleNamespace(
            type="content_block_start",
            content_block=SimpleNamespace(type="tool_use", id="tool-1", name="lookup"),
        ),
        SimpleNamespace(
            type="content_block_delta",
            delta=SimpleNamespace(type="text_delta", text="a" * 300),
        ),
        SimpleNamespace(
            type="content_block_delta",
            delta=SimpleNamespace(type="input_json_delta", partial_json='{"q"'),
        ),
        SimpleNamespace(
            type="message_delta",
            delta=SimpleNamespace(stop_reason="tool_use"),
            usage=SimpleNamespace(output_tokens=6),
        ),
        SimpleNamespace(type="message_stop"),
    ]
    client = AnthropicMessages(events)
    provider = _provider_without_constructor(
        AnthropicProvider, LLMConfig(provider="anthropic", model="claude-test")
    )
    provider.async_client = SimpleNamespace(messages=client)

    result = asyncio.run(
        provider.stream([ChatMessage(role=ChatRole.USER, content="hi")])
    )

    assert result.is_ok()
    chunks = asyncio.run(_collect(result.unwrap()))
    assert chunks[0].tool_call_delta == {
        "id": "tool-1",
        "name": "lookup",
        "arguments": {},
    }
    assert [len(chunk.content) for chunk in chunks if chunk.content] == [256, 44]
    assert "".join(chunk.content for chunk in chunks) == "a" * 300
    assert chunks[3].tool_call_delta == {"arguments": '{"q"'}
    assert chunks[-1].finish_reason == "tool_calls"
    assert chunks[-1].usage.prompt_tokens == 9
    assert chunks[-1].usage.completion_tokens == 6
    assert chunks[-1].usage.total_tokens == 15
    assert chunks[-1].request_id == "msg-stream-1"
    assert provider.get_usage_stats()["total_prompt_tokens"] == 9
    assert provider.get_usage_stats()["total_completion_tokens"] == 6
    assert client.kwargs["stream"] is True


def test_native_stream_request_failure_is_typed_result_error():
    class FailingCompletions:
        async def create(self, **kwargs):
            raise RuntimeError("offline")

    provider = _provider_without_constructor(
        OpenAIProvider, LLMConfig(provider="openai", model="gpt-test")
    )
    provider.async_client = SimpleNamespace(
        chat=SimpleNamespace(completions=FailingCompletions())
    )

    result = asyncio.run(
        provider.stream([ChatMessage(role=ChatRole.USER, content="hi")])
    )

    assert isinstance(result, Result)
    assert result.is_err()
    assert result.unwrap_err()["errorType"] == "LLM_STREAM_ERROR"


async def _collect(iterator):
    return [chunk async for chunk in iterator]
