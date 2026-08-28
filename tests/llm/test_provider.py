"""Tests for LLM provider base class and registry."""

from types import SimpleNamespace

import pytest

from maple.core.result import Result
from maple.llm.anthropic_provider import AnthropicProvider
from maple.llm.openai_provider import OpenAIProvider
from maple.llm.provider import LLMProvider, classify_provider_exception
from maple.llm.registry import LLMProviderRegistry
from maple.llm.types import (
    ChatMessage,
    ChatRole,
    ImageContent,
    LLMConfig,
    LLMResponse,
    ModelRetryPolicy,
    TokenUsage,
)


class MockProvider(LLMProvider):
    """Mock LLM provider for testing."""

    def __init__(self, config):
        super().__init__(config)
        self._response = LLMResponse(
            content="Mock response",
            model=config.model,
            finish_reason="stop",
            usage=TokenUsage(prompt_tokens=10, completion_tokens=5, total_tokens=15),
        )

    def complete(
        self, messages, tools=None, temperature=None, max_tokens=None, stop=None
    ):
        self._track_usage(self._response)
        return Result.ok(self._response)


class TestLLMProvider:
    def test_abstract_cannot_instantiate(self):
        config = LLMConfig(provider="test", model="test-model")
        with pytest.raises(TypeError):
            LLMProvider(config)

    def test_mock_provider_complete(self):
        config = LLMConfig(provider="mock", model="mock-model")
        provider = MockProvider(config)
        messages = [ChatMessage(role=ChatRole.USER, content="test")]
        result = provider.complete(messages)
        assert result.is_ok()
        resp = result.unwrap()
        assert resp.content == "Mock response"
        assert resp.finish_reason == "stop"

    def test_usage_tracking(self):
        config = LLMConfig(provider="mock", model="mock-model")
        provider = MockProvider(config)
        messages = [ChatMessage(role=ChatRole.USER, content="test")]

        provider.complete(messages)
        provider.complete(messages)

        stats = provider.get_usage_stats()
        assert stats["total_prompt_tokens"] == 20
        assert stats["total_completion_tokens"] == 10
        assert stats["provider"] == "mock"
        assert stats["model"] == "mock-model"

    def test_count_tokens_default(self):
        config = LLMConfig(provider="mock", model="mock-model")
        provider = MockProvider(config)
        count = provider.count_tokens("Hello world")
        assert count > 0

    def test_provider_exception_classification_is_conservative_and_retryable(self):
        class RateLimitError(Exception):
            status_code = 429

        class ServerError(Exception):
            status_code = 503

        class ProviderFailure(Exception):
            pass

        assert (
            classify_provider_exception(
                RateLimitError("slow down"), fallback="LLM_COMPLETION_ERROR"
            )
            == "LLM_RATE_LIMITED"
        )
        assert (
            classify_provider_exception(
                ServerError("unavailable"), fallback="LLM_COMPLETION_ERROR"
            )
            == "LLM_TRANSIENT_ERROR"
        )
        assert (
            classify_provider_exception(
                ProviderFailure("deadline"), fallback="LLM_COMPLETION_ERROR"
            )
            == "LLM_COMPLETION_ERROR"
        )
        assert (
            classify_provider_exception(
                TimeoutError("deadline"), fallback="LLM_COMPLETION_ERROR"
            )
            == "LLM_TIMEOUT"
        )

    def test_model_retry_policy_caps_backoff_and_rejects_unbounded_values(self):
        policy = ModelRetryPolicy(
            max_retries=3,
            base_delay_seconds=2,
            max_delay_seconds=3,
        )
        assert policy.delay_for_retry(1) == 2
        assert policy.delay_for_retry(2) == 3
        assert policy.delay_for_retry(3) == 3
        assert policy.is_retryable({"errorType": "LLM_TIMEOUT"})
        assert not policy.is_retryable({"errorType": "LLM_AUTHENTICATION_ERROR"})
        with pytest.raises(ValueError, match="max_retries"):
            ModelRetryPolicy(max_retries=4)
        with pytest.raises(ValueError, match="delay"):
            ModelRetryPolicy(base_delay_seconds=4, max_delay_seconds=3)

    def test_openai_and_anthropic_adapters_preserve_classified_failures(self):
        class RateLimitError(Exception):
            status_code = 429

        class FailingCompletions:
            def create(self, **kwargs):
                raise RateLimitError("retry later")

        class FailingMessages:
            def create(self, **kwargs):
                raise RateLimitError("retry later")

        openai_provider = object.__new__(OpenAIProvider)
        LLMProvider.__init__(
            openai_provider, LLMConfig(provider="openai", model="test")
        )
        openai_provider.client = SimpleNamespace(
            chat=SimpleNamespace(completions=FailingCompletions())
        )
        anthropic_provider = object.__new__(AnthropicProvider)
        LLMProvider.__init__(
            anthropic_provider, LLMConfig(provider="anthropic", model="test")
        )
        anthropic_provider.client = SimpleNamespace(messages=FailingMessages())
        messages = [ChatMessage(role=ChatRole.USER, content="hello")]

        assert openai_provider.complete(messages).unwrap_err()["errorType"] == (
            "LLM_RATE_LIMITED"
        )
        assert anthropic_provider.complete(messages).unwrap_err()["errorType"] == (
            "LLM_RATE_LIMITED"
        )

    def test_openai_formats_text_and_image_content(self):
        provider = object.__new__(OpenAIProvider)
        message = ChatMessage(
            role=ChatRole.USER,
            content=[
                "inspect this",
                ImageContent(source="https://example.com/image.png", detail="high"),
            ],
        )

        formatted = provider._format_message(message)

        assert formatted["content"] == [
            {"type": "text", "text": "inspect this"},
            {
                "type": "image_url",
                "image_url": {
                    "url": "https://example.com/image.png",
                    "detail": "high",
                },
            },
        ]

    def test_anthropic_formats_data_uri_and_rejects_remote_image(self):
        provider = object.__new__(AnthropicProvider)
        data_message = ChatMessage(
            role=ChatRole.USER,
            content=[
                "inspect this",
                ImageContent(source="data:image/png;base64,aW1hZ2U="),
            ],
        )

        formatted = provider._format_messages([data_message])

        assert formatted.is_ok()
        assert formatted.unwrap()[1][0]["content"][1] == {
            "type": "image",
            "source": {
                "type": "base64",
                "media_type": "image/png",
                "data": "aW1hZ2U=",
            },
        }

        remote = provider._format_messages(
            [
                ChatMessage(
                    role=ChatRole.USER,
                    content=[ImageContent(source="https://example.com/image.png")],
                )
            ]
        )

        assert remote.is_err()
        assert remote.unwrap_err()["errorType"] == "LLM_UNSUPPORTED_CONTENT"


class TestLLMProviderRegistry:
    def setup_method(self):
        # Save and restore original state
        self._original = dict(LLMProviderRegistry._providers)

    def teardown_method(self):
        LLMProviderRegistry._providers = self._original

    def test_register_and_create(self):
        LLMProviderRegistry.register("mock", MockProvider)
        config = LLMConfig(provider="mock", model="test")
        result = LLMProviderRegistry.create(config)
        assert result.is_ok()
        provider = result.unwrap()
        assert isinstance(provider, MockProvider)

    def test_create_unknown_provider(self):
        config = LLMConfig(provider="nonexistent_xyz", model="test")
        result = LLMProviderRegistry.create(config)
        assert result.is_err()
        err = result.unwrap_err()
        assert err["errorType"] == "UNKNOWN_PROVIDER"

    def test_available_providers(self):
        LLMProviderRegistry.register("mock", MockProvider)
        available = LLMProviderRegistry.available_providers()
        assert "mock" in available

    def test_auto_registers_known_providers(self):
        LLMProviderRegistry._ensure_registered()
        available = LLMProviderRegistry.available_providers()
        assert "openai" in available
        assert "anthropic" in available
