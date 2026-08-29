"""Offline completion-contract fixtures for built-in LLM providers."""

from types import SimpleNamespace

import pytest

from maple.llm.anthropic_provider import AnthropicProvider
from maple.llm.openai_provider import OpenAIProvider
from maple.llm.provider import LLMProvider
from maple.llm.types import (
    ChatMessage,
    ChatRole,
    ImageContent,
    LLMConfig,
    ToolDefinition,
)


class SyncResponseClient:
    def __init__(self, response):
        self.response = response
        self.kwargs = None

    def create(self, **kwargs):
        self.kwargs = kwargs
        return self.response


class AsyncResponseClient(SyncResponseClient):
    async def create(self, **kwargs):
        self.kwargs = kwargs
        return self.response


def _provider_without_constructor(provider_type, config):
    provider = object.__new__(provider_type)
    LLMProvider.__init__(provider, config)
    return provider


def _openai_response(**overrides):
    values = {
        "id": "chatcmpl-fixture",
        "model": "gpt-fixture",
        "choices": [
            SimpleNamespace(
                message=SimpleNamespace(
                    content="fixture response",
                    tool_calls=[
                        SimpleNamespace(
                            id="call-fixture",
                            function=SimpleNamespace(
                                name="lookup", arguments='{"query":"maple"}'
                            ),
                        )
                    ],
                ),
                finish_reason="tool_calls",
            )
        ],
        "usage": SimpleNamespace(
            prompt_tokens=11,
            completion_tokens=7,
            total_tokens=18,
        ),
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def _anthropic_response(**overrides):
    values = {
        "id": "msg-fixture",
        "model": "claude-fixture",
        "stop_reason": "end_turn",
        "content": [
            SimpleNamespace(type="text", text="fixture response"),
            SimpleNamespace(
                type="tool_use",
                id="tool-fixture",
                name="lookup",
                input={"query": "maple"},
            ),
        ],
        "usage": SimpleNamespace(input_tokens=11, output_tokens=7),
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def test_openai_sync_completion_contract_maps_payload_and_response():
    client = SyncResponseClient(_openai_response())
    provider = _provider_without_constructor(
        OpenAIProvider, LLMConfig(provider="openai", model="gpt-fixture")
    )
    provider.client = SimpleNamespace(chat=SimpleNamespace(completions=client))
    messages = [
        ChatMessage(role=ChatRole.SYSTEM, content="be concise"),
        ChatMessage(
            role=ChatRole.USER,
            content=[
                "inspect",
                ImageContent(source="https://example.com/image.png", detail="high"),
            ],
        ),
    ]

    result = provider.complete(
        messages,
        tools=[ToolDefinition("lookup", "Find data", {"type": "object"})],
        temperature=0,
        max_tokens=10,
        stop=["END"],
    )

    assert result.is_ok()
    response = result.unwrap()
    assert response.content == "fixture response"
    assert response.tool_calls[0].arguments == {"query": "maple"}
    assert response.usage.total_tokens == 18
    assert client.kwargs["temperature"] == 0
    assert client.kwargs["max_tokens"] == 10
    assert client.kwargs["stop"] == ["END"]
    assert client.kwargs["tools"][0]["function"]["name"] == "lookup"
    assert client.kwargs["messages"][1]["content"][1]["type"] == "image_url"


async def test_openai_async_completion_contract_uses_async_client():
    client = AsyncResponseClient(_openai_response())
    provider = _provider_without_constructor(
        OpenAIProvider, LLMConfig(provider="openai", model="gpt-fixture")
    )
    provider.async_client = SimpleNamespace(chat=SimpleNamespace(completions=client))

    result = await provider.complete_async(
        [ChatMessage(role=ChatRole.USER, content="inspect")]
    )

    assert result.is_ok()
    assert result.unwrap().content == "fixture response"
    assert client.kwargs["messages"] == [{"role": "user", "content": "inspect"}]


def test_anthropic_sync_completion_contract_maps_payload_and_response():
    client = SyncResponseClient(_anthropic_response())
    provider = _provider_without_constructor(
        AnthropicProvider, LLMConfig(provider="anthropic", model="claude-fixture")
    )
    provider.client = SimpleNamespace(messages=client)
    messages = [
        ChatMessage(role=ChatRole.SYSTEM, content="be concise"),
        ChatMessage(
            role=ChatRole.USER,
            content=[
                "inspect",
                ImageContent(source="data:image/png;base64,cG5n"),
            ],
        ),
    ]

    result = provider.complete(
        messages,
        tools=[ToolDefinition("lookup", "Find data", {"type": "object"})],
        temperature=0,
        max_tokens=10,
        stop=["END"],
    )

    assert result.is_ok()
    response = result.unwrap()
    assert response.content == "fixture response"
    assert response.tool_calls[0].arguments == {"query": "maple"}
    assert response.finish_reason == "stop"
    assert response.usage.total_tokens == 18
    assert client.kwargs["system"] == "be concise"
    assert client.kwargs["temperature"] == 0
    assert client.kwargs["max_tokens"] == 10
    assert client.kwargs["stop_sequences"] == ["END"]
    assert client.kwargs["tools"][0]["input_schema"]["type"] == "object"
    assert client.kwargs["messages"][0]["content"][1]["type"] == "image"


async def test_anthropic_async_completion_contract_uses_async_client():
    client = AsyncResponseClient(_anthropic_response())
    provider = _provider_without_constructor(
        AnthropicProvider, LLMConfig(provider="anthropic", model="claude-fixture")
    )
    provider.async_client = SimpleNamespace(messages=client)

    result = await provider.complete_async(
        [ChatMessage(role=ChatRole.USER, content="inspect")]
    )

    assert result.is_ok()
    assert result.unwrap().content == "fixture response"
    assert client.kwargs["messages"] == [{"role": "user", "content": "inspect"}]


@pytest.mark.parametrize("arguments", ["{", "[]"])
def test_openai_rejects_malformed_tool_arguments_before_accounting(arguments):
    response = _openai_response()
    response.choices[0].message.tool_calls[0].function.arguments = arguments
    client = SyncResponseClient(response)
    provider = _provider_without_constructor(
        OpenAIProvider, LLMConfig(provider="openai", model="gpt-fixture")
    )
    provider.client = SimpleNamespace(chat=SimpleNamespace(completions=client))

    result = provider.complete([])

    assert result.is_err()
    assert result.unwrap_err()["errorType"] == "LLM_PROVIDER_RESPONSE_INVALID"
    assert provider.get_usage_stats()["total_prompt_tokens"] == 0


def test_anthropic_rejects_non_object_tool_arguments_before_accounting():
    response = _anthropic_response()
    response.content[1].input = ["not", "an", "object"]
    client = SyncResponseClient(response)
    provider = _provider_without_constructor(
        AnthropicProvider, LLMConfig(provider="anthropic", model="claude-fixture")
    )
    provider.client = SimpleNamespace(messages=client)

    result = provider.complete([])

    assert result.is_err()
    assert result.unwrap_err()["errorType"] == "LLM_PROVIDER_RESPONSE_INVALID"
    assert provider.get_usage_stats()["total_prompt_tokens"] == 0


@pytest.mark.parametrize("provider_type", [OpenAIProvider, AnthropicProvider])
def test_provider_rejects_malformed_usage_without_mutating_counters(provider_type):
    if provider_type is OpenAIProvider:
        response = _openai_response(
            usage=SimpleNamespace(
                prompt_tokens=-1,
                completion_tokens=2,
                total_tokens=1,
            )
        )
        client = SyncResponseClient(response)
        provider = _provider_without_constructor(
            provider_type, LLMConfig(provider="openai", model="fixture")
        )
        provider.client = SimpleNamespace(chat=SimpleNamespace(completions=client))
    else:
        response = _anthropic_response(
            usage=SimpleNamespace(input_tokens=1, output_tokens="bad")
        )
        client = SyncResponseClient(response)
        provider = _provider_without_constructor(
            provider_type, LLMConfig(provider="anthropic", model="fixture")
        )
        provider.client = SimpleNamespace(messages=client)

    result = provider.complete([])

    assert result.is_err()
    assert result.unwrap_err()["errorType"] == "LLM_PROVIDER_RESPONSE_INVALID"
    assert provider.get_usage_stats()["total_prompt_tokens"] == 0


def test_provider_rejects_oversized_completion_before_accounting():
    response = _openai_response()
    response.choices[0].message.content = "x" * (1_048_576 + 1)
    client = SyncResponseClient(response)
    provider = _provider_without_constructor(
        OpenAIProvider, LLMConfig(provider="openai", model="gpt-fixture")
    )
    provider.client = SimpleNamespace(chat=SimpleNamespace(completions=client))

    result = provider.complete([])

    assert result.is_err()
    assert result.unwrap_err()["errorType"] == "LLM_PROVIDER_RESPONSE_INVALID"
    assert provider.get_usage_stats()["total_prompt_tokens"] == 0


def test_provider_rejects_non_json_native_tool_arguments_before_accounting():
    response = _anthropic_response()
    response.content[1].input = {1: "non-string key"}
    client = SyncResponseClient(response)
    provider = _provider_without_constructor(
        AnthropicProvider, LLMConfig(provider="anthropic", model="gpt-fixture")
    )
    provider.client = SimpleNamespace(messages=client)

    result = provider.complete([])

    assert result.is_err()
    assert result.unwrap_err()["errorType"] == "LLM_PROVIDER_RESPONSE_INVALID"
    assert provider.get_usage_stats()["total_prompt_tokens"] == 0


def test_provider_rejects_unencodable_completion_before_accounting():
    response = _openai_response()
    response.choices[0].message.content = chr(0xD800)
    client = SyncResponseClient(response)
    provider = _provider_without_constructor(
        OpenAIProvider, LLMConfig(provider="openai", model="gpt-fixture")
    )
    provider.client = SimpleNamespace(chat=SimpleNamespace(completions=client))

    result = provider.complete([])

    assert result.is_err()
    assert result.unwrap_err()["errorType"] == "LLM_PROVIDER_RESPONSE_INVALID"
    assert provider.get_usage_stats()["total_prompt_tokens"] == 0
