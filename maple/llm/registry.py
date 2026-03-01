"""
Copyright (C) 2025 Mahesh Vaijainthymala Krishnamoorthy (Mahesh Vaikri)

This file is part of MAPLE - Multi Agent Protocol Language Engine.

MAPLE - Multi Agent Protocol Language Engine is free software: you can redistribute it and/or
modify it under the terms of the GNU Affero General Public License as published by the Free Software
Foundation, either version 3 of the License, or (at your option) any later version.
MAPLE - Multi Agent Protocol Language Engine is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A
PARTICULAR PURPOSE. See the GNU Affero General Public License for more details. You should have
received a copy of the GNU Affero General Public License along with MAPLE - Multi Agent Protocol
Language Engine. If not, see <https://www.gnu.org/licenses/>.
"""

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
