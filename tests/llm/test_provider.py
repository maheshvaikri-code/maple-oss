"""Tests for LLM provider base class and registry."""

import pytest
from maple.llm.provider import LLMProvider
from maple.llm.registry import LLMProviderRegistry
from maple.llm.types import (
    ChatMessage, ChatRole, LLMConfig, LLMResponse, TokenUsage, ToolDefinition,
)
from maple.core.result import Result


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

    def complete(self, messages, tools=None, temperature=None, max_tokens=None, stop=None):
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
