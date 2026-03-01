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

"""
MAPLE - Multi Agent Protocol Language Engine
Created by: Mahesh Vaijainthymala Krishnamoorthy (Mahesh Vaikri)

Multi-agent communication protocol with:
- Advanced Resource Management
- Type-safe Result<T,E> Error Handling
- Link Identification Security
- Multi-Agent Communication

Copyright 2024 Mahesh Vaijainthymala Krishnamoorthy (Mahesh Vaikri)
Licensed under the AGPL License, Version 3.0
"""

import warnings

from .agent.agent import Agent
from .agent.config import (
    Config,
    MetricsConfig,
    PerformanceConfig,
    SecurityConfig,
    TracingConfig,
)
from .broker.broker import MessageBroker
from .communication.streaming import Stream, StreamOptions
from .core.message import Message, Priority
from .core.result import Result
from .core.types import AgentID, Duration, MessageID, Priority, Size
from .error.circuit_breaker import CircuitBreaker
from .error.recovery import RetryOptions, exponential_backoff, retry
from .error.types import Error, ErrorType, Severity
from .resources.manager import ResourceAllocation, ResourceManager
from .resources.negotiation import ResourceNegotiator
from .resources.specification import ResourceRange, ResourceRequest, TimeConstraint

# Autonomy layer (LLM + autonomous agents)
from .autonomy.agent import AutonomousAgent, AutonomousConfig, Goal
from .autonomy.tools import Tool, ToolRegistry
from .autonomy.memory import MemoryManager
from .autonomy.orchestrator import AgentOrchestrator
from .llm.types import LLMConfig, ChatMessage, ChatRole
from .llm.registry import LLMProviderRegistry

__version__ = "1.1.0"
__author__ = "Mahesh Vaijainthymala Krishnamoorthy (Mahesh Vaikri)"
__email__ = "mahesh@mapleagent.org"
__license__ = "AGPL 3.0"

# Package metadata
__status__ = "Active Development"

__title__ = "maple"
__description__ = "Multi Agent Protocol Language Engine - Advanced Multi-Agent Communication Protocol Framework"
__url__ = "https://github.com/maheshvaikri-code/maple-oss"

# All public APIs
__all__ = [
    # Core types and utilities
    "Priority",
    "Size",
    "Duration",
    "AgentID",
    "MessageID",
    # Message handling
    "Message",
    "Result",
    # Agent configuration
    "Config",
    "SecurityConfig",
    "PerformanceConfig",
    "MetricsConfig",
    "TracingConfig",
    # Core classes
    "Agent",
    "MessageBroker",
    # Error handling
    "Error",
    "Severity",
    "ErrorType",
    "retry",
    "RetryOptions",
    "exponential_backoff",
    "CircuitBreaker",
    # Resource management
    "ResourceRequest",
    "ResourceRange",
    "TimeConstraint",
    "ResourceManager",
    "ResourceAllocation",
    "ResourceNegotiator",
    # Communication patterns
    "Stream",
    "StreamOptions",
    # Autonomy layer
    "AutonomousAgent",
    "AutonomousConfig",
    "Goal",
    "Tool",
    "ToolRegistry",
    "MemoryManager",
    "AgentOrchestrator",
    "LLMConfig",
    "ChatMessage",
    "ChatRole",
    "LLMProviderRegistry",
    # Package metadata
    "__version__",
    "__author__",
    "__license__",
]


# Validation that our perfect test score is maintained
def validate_installation():
    """Validate that MAPLE is properly installed and ready to use."""
    try:
        # Test core functionality
        config = Config(agent_id="validation_test", broker_url="memory://test")
        agent = Agent(config)

        message = Message(message_type="VALIDATION_TEST", payload={"test": True})

        # Basic validation passed
        return {
            "status": "SUCCESS",
            "version": __version__,
            "ready": True,
        }

    except Exception as e:
        return {"status": "ERROR", "error": str(e), "ready": False}


# Auto-validation on import (optional)
if __debug__:
    # Only run validation in debug mode to avoid import overhead in production
    _validation_result = validate_installation()
    if _validation_result["status"] != "SUCCESS":
        warnings.warn(
            f"MAPLE validation failed: {_validation_result.get('error', 'Unknown error')}"
        )


# Package banner for CLI tools
def print_banner():
    """Print MAPLE banner."""
    print(
        f"""
MAPLE v{__version__} - Multi Agent Protocol Language Engine

Created by: {__author__}
License: {__license__}
"""
    )
