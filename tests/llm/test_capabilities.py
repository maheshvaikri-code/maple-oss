"""Tests for capability-aware provider selection."""

from maple.core.result import Result
from maple.llm.capabilities import (
    ProviderCapabilities,
    ProviderRequirements,
    ProviderRouter,
)
from maple.llm.provider import LLMProvider
from maple.llm.types import LLMConfig


class MockProvider(LLMProvider):
    def complete(
        self, messages, tools=None, temperature=None, max_tokens=None, stop=None
    ):
        return Result.ok(None)


class FailingProvider(LLMProvider):
    def __init__(self, config):
        raise RuntimeError("provider unavailable")

    def complete(
        self, messages, tools=None, temperature=None, max_tokens=None, stop=None
    ):
        return Result.ok(None)


def test_router_selects_declared_capabilities_in_priority_order():
    router = ProviderRouter()
    router.register(
        "basic",
        MockProvider,
        ProviderCapabilities(tools=True, max_context_tokens=8_000),
        priority=1,
    )
    router.register(
        "streaming",
        MockProvider,
        ProviderCapabilities(tools=True, streaming=True, max_context_tokens=16_000),
        priority=5,
    )

    result = router.select(
        ProviderRequirements(tools=True, streaming=True, min_context_tokens=12_000)
    )

    assert result.is_ok()
    assert [descriptor.name for descriptor in result.unwrap()] == ["streaming"]


def test_router_selects_image_capable_provider_only_for_image_requirements():
    router = ProviderRouter()
    router.register(
        "text",
        MockProvider,
        ProviderCapabilities(tools=True),
        priority=2,
    )
    router.register(
        "vision",
        MockProvider,
        ProviderCapabilities(tools=True, image_input=True),
        priority=1,
    )

    result = router.select(ProviderRequirements(image_input=True))

    assert result.is_ok()
    assert [descriptor.name for descriptor in result.unwrap()] == ["vision"]


def test_router_selects_native_async_provider_only_for_async_requirements():
    router = ProviderRouter()
    router.register(
        "sync-fallback",
        MockProvider,
        ProviderCapabilities(streaming=True),
        priority=2,
    )
    router.register(
        "native-async",
        MockProvider,
        ProviderCapabilities(async_completion=True),
        priority=1,
    )

    result = router.select(ProviderRequirements(async_completion=True))

    assert result.is_ok()
    assert [descriptor.name for descriptor in result.unwrap()] == ["native-async"]


def test_router_falls_back_when_high_priority_provider_initialization_fails():
    router = ProviderRouter()
    router.register(
        "broken",
        FailingProvider,
        ProviderCapabilities(tools=True),
        priority=10,
    )
    router.register(
        "working",
        MockProvider,
        ProviderCapabilities(tools=True),
        priority=1,
    )
    configs = {
        "broken": LLMConfig(provider="broken", model="test"),
        "working": LLMConfig(provider="working", model="test"),
    }

    result = router.create(configs, ProviderRequirements(tools=True))

    assert result.is_ok()
    assert isinstance(result.unwrap(), MockProvider)


def test_router_fails_closed_when_no_provider_is_capable_or_configured():
    router = ProviderRouter()
    router.register("basic", MockProvider, ProviderCapabilities(tools=False))

    incapable = router.select(ProviderRequirements(tools=True))
    missing_config = router.create({}, ProviderRequirements())

    assert incapable.is_err()
    assert incapable.unwrap_err()["errorType"] == "NO_CAPABLE_PROVIDER"
    assert missing_config.is_err()
    assert missing_config.unwrap_err()["errorType"] == "PROVIDER_SELECTION_FAILED"
