"""Tests for capability-aware provider selection."""

from maple.core.result import Result
from maple.llm.capabilities import (
    FallbackLLMProvider,
    ProviderCapabilities,
    ProviderRequirements,
    ProviderRouter,
)
from maple.llm.provider import LLMProvider
from maple.llm.types import ChatMessage, ChatRole, LLMConfig, LLMResponse


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


class ScriptedProvider(LLMProvider):
    def __init__(self, config, responses):
        super().__init__(config)
        self.responses = list(responses)
        self.calls = 0

    def complete(
        self, messages, tools=None, temperature=None, max_tokens=None, stop=None
    ):
        self.calls += 1
        return self.responses.pop(0)


class RouterProvider(LLMProvider):
    def __init__(self, config):
        super().__init__(config)
        self.calls = 0

    def complete(
        self, messages, tools=None, temperature=None, max_tokens=None, stop=None
    ):
        self.calls += 1
        if self.config.provider == "primary":
            return Result.err({"errorType": "LLM_TRANSIENT_ERROR", "message": "retry"})
        return Result.ok(LLMResponse(content="backup", model=self.config.model))


class AsyncScriptedProvider(ScriptedProvider):
    async def complete_async(
        self, messages, tools=None, temperature=None, max_tokens=None, stop=None
    ):
        self.calls += 1
        return self.responses.pop(0)


class RaisingProvider(LLMProvider):
    def complete(
        self, messages, tools=None, temperature=None, max_tokens=None, stop=None
    ):
        raise TimeoutError("provider timed out")


class InvalidResultProvider(LLMProvider):
    def complete(
        self, messages, tools=None, temperature=None, max_tokens=None, stop=None
    ):
        return "not a Result"


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


def test_fallback_provider_retries_transient_sync_error_in_order():
    response = LLMResponse(content="backup", model="backup-model")
    primary = ScriptedProvider(
        LLMConfig(provider="primary", model="primary-model"),
        [Result.err({"errorType": "LLM_RATE_LIMITED", "message": "retry"})],
    )
    backup = ScriptedProvider(
        LLMConfig(provider="backup", model="backup-model"),
        [Result.ok(response)],
    )
    fallback = FallbackLLMProvider([primary, backup])

    result = fallback.complete([ChatMessage(role=ChatRole.USER, content="hello")])

    assert result.is_ok()
    assert result.unwrap() is response
    assert primary.calls == 1
    assert backup.calls == 1
    assert fallback.provider_names == ("primary", "backup")
    assert fallback.get_usage_stats()["provider"] == "fallback"


def test_fallback_provider_classifies_raised_timeout_before_failover():
    backup = ScriptedProvider(
        LLMConfig(provider="backup", model="backup-model"),
        [Result.ok(LLMResponse(content="backup"))],
    )
    fallback = FallbackLLMProvider(
        [RaisingProvider(LLMConfig(provider="primary", model="primary-model")), backup]
    )

    result = fallback.complete([])

    assert result.is_ok()
    assert result.unwrap().content == "backup"
    assert backup.calls == 1


def test_fallback_provider_rejects_malformed_provider_result_without_failover():
    backup = ScriptedProvider(
        LLMConfig(provider="backup", model="backup-model"),
        [Result.ok(LLMResponse(content="unused"))],
    )
    fallback = FallbackLLMProvider(
        [
            InvalidResultProvider(LLMConfig(provider="primary", model="primary-model")),
            backup,
        ]
    )

    result = fallback.complete([])

    assert result.is_err()
    assert result.unwrap_err()["errorType"] == "LLM_PROVIDER_RESULT_INVALID"
    assert backup.calls == 0


async def test_fallback_provider_retries_transient_async_error_in_order():
    response = LLMResponse(content="async backup", model="backup-model")
    primary = AsyncScriptedProvider(
        LLMConfig(provider="primary", model="primary-model"),
        [Result.err({"errorType": "LLM_TIMEOUT", "message": "retry"})],
    )
    backup = AsyncScriptedProvider(
        LLMConfig(provider="backup", model="backup-model"),
        [Result.ok(response)],
    )
    fallback = FallbackLLMProvider([primary, backup])

    result = await fallback.complete_async([])

    assert result.is_ok()
    assert result.unwrap() is response
    assert primary.calls == 1
    assert backup.calls == 1


def test_fallback_provider_fails_fast_and_reports_exhausted_attempts():
    primary = ScriptedProvider(
        LLMConfig(provider="primary", model="primary-model"),
        [Result.err({"errorType": "LLM_AUTHENTICATION_ERROR", "message": "denied"})],
    )
    backup = ScriptedProvider(
        LLMConfig(provider="backup", model="backup-model"),
        [Result.ok(LLMResponse(content="unused"))],
    )
    fail_fast = FallbackLLMProvider([primary, backup])

    result = fail_fast.complete([])

    assert result.is_err()
    assert result.unwrap_err()["errorType"] == "LLM_AUTHENTICATION_ERROR"
    assert backup.calls == 0

    exhausted_primary = ScriptedProvider(
        LLMConfig(provider="primary", model="primary-model"),
        [Result.err({"errorType": "LLM_TIMEOUT", "message": "slow"})],
    )
    exhausted_backup = ScriptedProvider(
        LLMConfig(provider="backup", model="backup-model"),
        [Result.err({"errorType": "LLM_TRANSIENT_ERROR", "message": "down"})],
    )
    exhausted = FallbackLLMProvider([exhausted_primary, exhausted_backup]).complete([])

    assert exhausted.is_err()
    assert exhausted.unwrap_err()["errorType"] == "LLM_TRANSIENT_ERROR"
    assert exhausted.unwrap_err()["details"] == {
        "attemptedProviders": ["primary", "backup"]
    }


async def test_fallback_provider_rejects_streaming_without_partial_continuation():
    fallback = FallbackLLMProvider(
        [ScriptedProvider(LLMConfig(provider="primary", model="model"), [])]
    )

    result = await fallback.stream([])

    assert result.is_err()
    assert result.unwrap_err()["errorType"] == "PROVIDER_FAILOVER_STREAM_UNSUPPORTED"


def test_router_creates_opt_in_fallback_and_rejects_stream_requirement():
    router = ProviderRouter()
    router.register(
        "primary",
        RouterProvider,
        ProviderCapabilities(tools=True),
        priority=10,
    )
    router.register(
        "backup",
        RouterProvider,
        ProviderCapabilities(tools=True),
        priority=1,
    )
    configs = {
        "primary": LLMConfig(provider="primary", model="primary-model"),
        "backup": LLMConfig(provider="backup", model="backup-model"),
    }

    result = router.create(configs, failover=True)
    streamed = router.create(
        configs,
        ProviderRequirements(streaming=True),
        failover=True,
    )

    assert result.is_ok()
    assert isinstance(result.unwrap(), FallbackLLMProvider)
    assert result.unwrap().complete([]).unwrap().content == "backup"
    assert streamed.is_err()
    assert streamed.unwrap_err()["errorType"] == "PROVIDER_FAILOVER_STREAM_UNSUPPORTED"


def test_router_fails_closed_when_failover_provider_bound_is_exceeded():
    router = ProviderRouter()
    configs = {}
    for index in range(9):
        name = f"provider-{index}"
        router.register(name, MockProvider, ProviderCapabilities())
        configs[name] = LLMConfig(provider=name, model="model")

    result = router.create(configs, failover=True)

    assert result.is_err()
    assert result.unwrap_err()["errorType"] == "PROVIDER_FAILOVER_LIMIT_EXCEEDED"
