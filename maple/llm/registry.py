"""LLM Provider registry for MAPLE."""

import logging
from typing import Dict, Type

from ..core.result import Result
from .provider import LLMProvider
from .types import LLMConfig

logger = logging.getLogger(__name__)


class LLMProviderRegistry:
    """Registry for LLM providers. Enables plug-and-play provider switching."""

    _providers: Dict[str, Type[LLMProvider]] = {}

    @classmethod
    def register(cls, name: str, provider_class: Type[LLMProvider]) -> None:
        """Register an LLM provider class."""
        cls._providers[name] = provider_class
        logger.info(f"Registered LLM provider: {name}")

    @classmethod
    def create(cls, config: LLMConfig) -> Result[LLMProvider, Dict]:
        """Create an LLM provider instance from config."""
        cls._ensure_registered()
        if config.provider not in cls._providers:
            return Result.err({
                'errorType': 'UNKNOWN_PROVIDER',
                'message': f'LLM provider "{config.provider}" not registered. '
                           f'Available: {list(cls._providers.keys())}'
            })
        try:
            provider = cls._providers[config.provider](config)
            return Result.ok(provider)
        except Exception as e:
            return Result.err({
                'errorType': 'PROVIDER_INIT_ERROR',
                'message': str(e)
            })

    @classmethod
    def available_providers(cls) -> list:
        """List registered provider names."""
        cls._ensure_registered()
        return list(cls._providers.keys())

    @classmethod
    def _ensure_registered(cls):
        """Auto-register built-in providers on first use."""
        if cls._providers:
            return
        try:
            from .openai_provider import OpenAIProvider
            cls._providers["openai"] = OpenAIProvider
        except ImportError:
            pass
        try:
            from .anthropic_provider import AnthropicProvider
            cls._providers["anthropic"] = AnthropicProvider
        except ImportError:
            pass
