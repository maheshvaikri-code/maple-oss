"""Capability-aware provider selection and fallback primitives."""

from __future__ import annotations

from dataclasses import dataclass
from typing import (
    Any,
    AsyncIterator,
    Dict,
    List,
    Mapping,
    Optional,
    Sequence,
    Tuple,
    Type,
)

from ..core.result import Result
from .provider import LLMProvider, classify_provider_exception
from .types import ChatMessage, LLMChunk, LLMConfig, LLMResponse, ToolDefinition

Error = Dict[str, Any]

_MAX_FAILOVER_PROVIDERS = 8
_DEFAULT_FAILOVER_ERROR_TYPES = (
    "LLM_RATE_LIMITED",
    "LLM_TIMEOUT",
    "LLM_TRANSIENT_ERROR",
)


def _valid_error_type(value: Any) -> bool:
    return (
        isinstance(value, str)
        and bool(value)
        and len(value) <= 64
        and all(
            character.isupper() or character.isdigit() or character == "_"
            for character in value
        )
    )


def _validate_failover_error_types(value: Any) -> Tuple[str, ...]:
    if (
        not isinstance(value, tuple)
        or not value
        or len(value) > 16
        or any(not _valid_error_type(item) for item in value)
    ):
        raise ValueError(
            "fallback_error_types must be a tuple of 1 to 16 uppercase identifiers"
        )
    return value


def _safe_provider_label(provider: LLMProvider) -> str:
    configured = getattr(getattr(provider, "config", None), "provider", None)
    if (
        isinstance(configured, str)
        and configured
        and len(configured) <= 128
        and all(
            ord(character) >= 32 and ord(character) != 127 for character in configured
        )
    ):
        return configured
    return type(provider).__name__[:128] or "provider"


def _exception_error(error_type: str, provider: LLMProvider, exc: Exception) -> Error:
    return {
        "errorType": error_type,
        "message": "provider completion failed before a response was returned.",
        "details": {
            "provider": _safe_provider_label(provider),
            "exception": type(exc).__name__[:128],
        },
    }


def _result_error(error: Any) -> Optional[Error]:
    if not isinstance(error, Mapping):
        return None
    error_type = error.get("errorType")
    if not _valid_error_type(error_type):
        return None
    return dict(error)


def _exhausted_error(error_type: str, attempted: Sequence[str]) -> Error:
    return {
        "errorType": error_type,
        "message": "all configured providers failed during completion.",
        "details": {"attemptedProviders": list(attempted[:_MAX_FAILOVER_PROVIDERS])},
    }


class FallbackLLMProvider(LLMProvider):
    """Sequentially fail over bounded LLM completion requests.

    This wrapper is opt-in and completion-only. It does not share circuit or
    health state, does not retry a provider twice for one request, and rejects
    native streaming so callers cannot mistake a fallback for stream
    continuity.
    """

    def __init__(
        self,
        providers: Sequence[LLMProvider],
        *,
        fallback_error_types: Tuple[str, ...] = _DEFAULT_FAILOVER_ERROR_TYPES,
    ) -> None:
        if isinstance(providers, (str, bytes)) or not isinstance(providers, Sequence):
            raise ValueError(
                "providers must be a bounded sequence of LLMProvider values"
            )
        provider_tuple = tuple(providers)
        if not 1 <= len(provider_tuple) <= _MAX_FAILOVER_PROVIDERS:
            raise ValueError(
                f"providers must contain 1 to {_MAX_FAILOVER_PROVIDERS} values"
            )
        if any(not isinstance(provider, LLMProvider) for provider in provider_tuple):
            raise ValueError("providers must contain only LLMProvider values")
        self._providers = provider_tuple
        self._fallback_error_types = _validate_failover_error_types(
            fallback_error_types
        )
        super().__init__(provider_tuple[0].config)

    @property
    def provider_names(self) -> Tuple[str, ...]:
        """Return bounded child-provider labels in attempt order."""
        return tuple(_safe_provider_label(provider) for provider in self._providers)

    def get_usage_stats(self) -> Dict[str, Any]:
        """Return wrapper-owned usage with bounded child labels."""
        stats = super().get_usage_stats()
        stats["provider"] = "fallback"
        stats["providers"] = list(self.provider_names)
        return stats

    def _should_fail_over(self, error_type: str) -> bool:
        return error_type in self._fallback_error_types

    def _success(self, result: Result[Any, Any]) -> Result[Any, Any]:
        response = result.unwrap()
        if isinstance(response, LLMResponse):
            self._track_usage(response)
        return result

    def complete(
        self,
        messages: List[ChatMessage],
        tools: Optional[List[ToolDefinition]] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        stop: Optional[List[str]] = None,
    ) -> Result[LLMResponse, Dict[str, Any]]:
        """Try each child once, advancing only on configured transient errors."""
        attempted: List[str] = []
        for provider in self._providers:
            attempted.append(_safe_provider_label(provider))
            try:
                result = provider.complete(
                    messages,
                    tools=tools,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    stop=stop,
                )
            except Exception as exc:
                error_type = classify_provider_exception(
                    exc, fallback="LLM_COMPLETION_ERROR"
                )
                failure = _exception_error(error_type, provider, exc)
            else:
                if not isinstance(result, Result):
                    return Result.err(
                        {
                            "errorType": "LLM_PROVIDER_RESULT_INVALID",
                            "message": "provider completion returned an invalid result.",
                        }
                    )
                if result.is_ok():
                    return self._success(result)
                normalized_error = _result_error(result.unwrap_err())
                if normalized_error is None:
                    return Result.err(
                        {
                            "errorType": "LLM_PROVIDER_RESULT_INVALID",
                            "message": "provider completion returned an invalid error.",
                        }
                    )
                failure = normalized_error
                error_type = normalized_error["errorType"]

            if not self._should_fail_over(error_type):
                return Result.err(failure)
            if len(attempted) == len(self._providers):
                return Result.err(_exhausted_error(error_type, attempted))
        return Result.err(
            {
                "errorType": "LLM_PROVIDER_RESULT_INVALID",
                "message": "provider failover completed without a result.",
            }
        )

    async def complete_async(
        self,
        messages: List[ChatMessage],
        tools: Optional[List[ToolDefinition]] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        stop: Optional[List[str]] = None,
    ) -> Result[LLMResponse, Dict[str, Any]]:
        """Async counterpart with the same bounded failover semantics."""
        attempted: List[str] = []
        for provider in self._providers:
            attempted.append(_safe_provider_label(provider))
            try:
                result = await provider.complete_async(
                    messages,
                    tools=tools,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    stop=stop,
                )
            except Exception as exc:
                error_type = classify_provider_exception(
                    exc, fallback="LLM_COMPLETION_ERROR"
                )
                failure = _exception_error(error_type, provider, exc)
            else:
                if not isinstance(result, Result):
                    return Result.err(
                        {
                            "errorType": "LLM_PROVIDER_RESULT_INVALID",
                            "message": "provider completion returned an invalid result.",
                        }
                    )
                if result.is_ok():
                    return self._success(result)
                normalized_error = _result_error(result.unwrap_err())
                if normalized_error is None:
                    return Result.err(
                        {
                            "errorType": "LLM_PROVIDER_RESULT_INVALID",
                            "message": "provider completion returned an invalid error.",
                        }
                    )
                failure = normalized_error
                error_type = normalized_error["errorType"]

            if not self._should_fail_over(error_type):
                return Result.err(failure)
            if len(attempted) == len(self._providers):
                return Result.err(_exhausted_error(error_type, attempted))
        return Result.err(
            {
                "errorType": "LLM_PROVIDER_RESULT_INVALID",
                "message": "provider failover completed without a result.",
            }
        )

    async def stream(
        self,
        messages: List[ChatMessage],
        tools: Optional[List[ToolDefinition]] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> Result[AsyncIterator[LLMChunk], Dict[str, Any]]:
        """Reject streaming because failover cannot continue a partial stream."""
        return Result.err(
            {
                "errorType": "PROVIDER_FAILOVER_STREAM_UNSUPPORTED",
                "message": "provider failover supports completion, not native streaming.",
            }
        )


@dataclass(frozen=True)
class ProviderCapabilities:
    """Explicit capabilities declared by one provider/model family."""

    tools: bool = False
    streaming: bool = False
    async_completion: bool = False
    structured_output: bool = False
    image_input: bool = False
    max_context_tokens: Optional[int] = None

    def supports(self, requirements: "ProviderRequirements") -> bool:
        """Return whether this declaration satisfies the requirements."""
        if requirements.tools and not self.tools:
            return False
        if requirements.streaming and not self.streaming:
            return False
        if requirements.async_completion and not self.async_completion:
            return False
        if requirements.structured_output and not self.structured_output:
            return False
        if requirements.image_input and not self.image_input:
            return False
        if requirements.min_context_tokens:
            if self.max_context_tokens is None:
                return False
            if self.max_context_tokens < requirements.min_context_tokens:
                return False
        return True


@dataclass(frozen=True)
class ProviderRequirements:
    """Capabilities required by an agent task."""

    tools: bool = False
    streaming: bool = False
    async_completion: bool = False
    structured_output: bool = False
    image_input: bool = False
    min_context_tokens: int = 0

    def validate(self) -> Optional[Error]:
        if (
            not isinstance(self.min_context_tokens, int)
            or isinstance(self.min_context_tokens, bool)
            or self.min_context_tokens < 0
        ):
            return {
                "errorType": "PROVIDER_REQUIREMENTS_INVALID",
                "message": "min_context_tokens must be a non-negative integer.",
            }
        for name in (
            "tools",
            "streaming",
            "async_completion",
            "structured_output",
            "image_input",
        ):
            if not isinstance(getattr(self, name), bool):
                return {
                    "errorType": "PROVIDER_REQUIREMENTS_INVALID",
                    "message": f"{name} must be boolean.",
                }
        return None


@dataclass(frozen=True)
class ProviderDescriptor:
    """Provider factory, capability declaration, and fallback priority."""

    name: str
    factory: Type[LLMProvider]
    capabilities: ProviderCapabilities
    priority: int = 0


class ProviderRouter:
    """Select and instantiate providers using declared capabilities."""

    def __init__(self) -> None:
        self._providers: Dict[str, ProviderDescriptor] = {}

    def register(
        self,
        name: str,
        factory: Type[LLMProvider],
        capabilities: ProviderCapabilities,
        *,
        priority: int = 0,
    ) -> Result[None, Error]:
        """Register or replace a named provider descriptor."""
        if not isinstance(name, str) or not name or len(name) > 128:
            return Result.err(
                {
                    "errorType": "PROVIDER_REGISTRATION_INVALID",
                    "message": "provider name must be bounded and non-empty.",
                }
            )
        if not isinstance(priority, int) or isinstance(priority, bool):
            return Result.err(
                {
                    "errorType": "PROVIDER_REGISTRATION_INVALID",
                    "message": "provider priority must be an integer.",
                }
            )
        if not isinstance(capabilities, ProviderCapabilities) or not isinstance(
            factory, type
        ):
            return Result.err(
                {
                    "errorType": "PROVIDER_REGISTRATION_INVALID",
                    "message": "provider factory and capabilities are invalid.",
                }
            )
        self._providers[name] = ProviderDescriptor(
            name=name,
            factory=factory,
            capabilities=capabilities,
            priority=priority,
        )
        return Result.ok(None)

    def select(
        self, requirements: Optional[ProviderRequirements] = None
    ) -> Result[List[ProviderDescriptor], Error]:
        """Return compatible descriptors in deterministic fallback order."""
        requirements = requirements or ProviderRequirements()
        requirements_error = requirements.validate()
        if requirements_error is not None:
            return Result.err(requirements_error)
        selected = [
            descriptor
            for descriptor in self._providers.values()
            if descriptor.capabilities.supports(requirements)
        ]
        selected.sort(key=lambda descriptor: (-descriptor.priority, descriptor.name))
        if not selected:
            return Result.err(
                {
                    "errorType": "NO_CAPABLE_PROVIDER",
                    "message": "No registered provider satisfies the requirements.",
                }
            )
        return Result.ok(selected)

    def create(
        self,
        configs: Mapping[str, LLMConfig],
        requirements: Optional[ProviderRequirements] = None,
        *,
        failover: bool = False,
    ) -> Result[LLMProvider, Error]:
        """Instantiate a compatible provider, optionally with bounded failover.

        The default returns the first configured provider. With ``failover``
        enabled, all configured compatible providers are initialized in
        selection order and wrapped for completion-only transient failover.
        """
        if not isinstance(failover, bool):
            return Result.err(
                {
                    "errorType": "PROVIDER_SELECTION_INVALID",
                    "message": "failover must be a boolean.",
                }
            )
        if failover and requirements is not None and requirements.streaming:
            requirements_error = requirements.validate()
            if requirements_error is not None:
                return Result.err(requirements_error)
            return Result.err(
                {
                    "errorType": "PROVIDER_FAILOVER_STREAM_UNSUPPORTED",
                    "message": "provider failover does not support native streaming.",
                }
            )
        selected = self.select(requirements)
        if selected.is_err():
            return Result.err(selected.unwrap_err())
        configured = [
            descriptor
            for descriptor in selected.unwrap()
            if configs.get(descriptor.name) is not None
        ]
        if failover and len(configured) > _MAX_FAILOVER_PROVIDERS:
            return Result.err(
                {
                    "errorType": "PROVIDER_FAILOVER_LIMIT_EXCEEDED",
                    "message": "provider failover is limited to eight providers.",
                    "details": {"maxProviders": _MAX_FAILOVER_PROVIDERS},
                }
            )
        attempted: List[str] = []
        providers: List[LLMProvider] = []
        for descriptor in configured:
            config = configs.get(descriptor.name)
            if config is None:
                continue
            attempted.append(descriptor.name)
            try:
                provider = descriptor.factory(config)
            except Exception:
                continue
            if failover:
                providers.append(provider)
            else:
                return Result.ok(provider)
        if failover and providers:
            return Result.ok(FallbackLLMProvider(providers))
        return Result.err(
            {
                "errorType": "PROVIDER_SELECTION_FAILED",
                "message": "No compatible configured provider could be initialized.",
                "details": {"attempted": attempted},
            }
        )

    def names(self) -> List[str]:
        """Return registered provider names."""
        return sorted(self._providers)
