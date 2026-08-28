"""Capability-aware provider selection and fallback primitives."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Mapping, Optional, Type

from ..core.result import Result
from .provider import LLMProvider
from .types import LLMConfig

Error = Dict[str, Any]


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
    ) -> Result[LLMProvider, Error]:
        """Instantiate the first compatible configured provider."""
        selected = self.select(requirements)
        if selected.is_err():
            return Result.err(selected.unwrap_err())
        attempted: List[str] = []
        for descriptor in selected.unwrap():
            config = configs.get(descriptor.name)
            if config is None:
                continue
            attempted.append(descriptor.name)
            try:
                return Result.ok(descriptor.factory(config))
            except Exception:
                continue
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
