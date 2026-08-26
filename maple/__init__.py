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

# MAPLE - Multi Agent Protocol Language Engine.
# Created by: Mahesh Vaijainthymala Krishnamoorthy (Mahesh Vaikri).
# Multi-agent communication protocol with advanced resource management,
# type-safe Result<T,E> error handling, link identification security, and
# multi-agent communication.

import warnings
from typing import Any, Dict

from .agent.agent import Agent
from .agent.config import (
    Config,
    MetricsConfig,
    PerformanceConfig,
    SecurityConfig,
    TracingConfig,
)

# Autonomy layer (LLM + autonomous agents)
from .autonomy.agent import AutonomousAgent, AutonomousConfig, Goal
from .autonomy.approval import (
    ApprovalDecision,
    ApprovalRequest,
    ApprovalStore,
    FileApprovalStore,
    InMemoryApprovalStore,
)
from .autonomy.artifacts import (
    Artifact,
    ArtifactStore,
    CodeBlock,
    FileArtifactStore,
    InMemoryArtifactStore,
    extract_code_blocks,
)
from .autonomy.contracts import (
    Guardrail,
    parse_structured_output,
    parse_typed_output,
    run_guardrails,
    schema_guardrail,
    structured_model_schema,
    validate_json_schema,
    validate_typed_value,
)
from .autonomy.evaluation import (
    EvalCase,
    EvalJudge,
    EvalJudgeResult,
    EvalObservation,
    EvalReport,
    EvalResult,
    EvaluationHarness,
    GroundednessEvalCase,
    GroundednessObservation,
    GroundingSource,
    RetrievalEvalCase,
)
from .autonomy.events import (
    AgentEvent,
    EventBatch,
    EventCursor,
    EventExporter,
    EventStream,
    RedactionPolicy,
)
from .autonomy.interactions import (
    FileHumanInputStore,
    HumanInputAuthorizer,
    HumanInputDecision,
    HumanInputNotification,
    HumanInputNotifier,
    HumanInputRound,
    HumanInputRequest,
    HumanInputStore,
    InMemoryHumanInputStore,
)
from .autonomy.execution import (
    CancellationToken,
    ExecutionExecutor,
    ExecutionPolicy,
    TrustedLocalExecutor,
)
from .autonomy.interop import InteropEnvelope, round_trip_json
from .autonomy.handoffs import (
    FileHandoffStore,
    HandoffRecord,
    HandoffStore,
    InMemoryHandoffStore,
)
from .autonomy.memory import MemoryManager
from .autonomy.orchestrator import AgentOrchestrator
from .autonomy.replay import (
    DEFAULT_MAX_RECORD_BYTES,
    DEFAULT_MAX_RECORDS,
    DEFAULT_MAX_RUN_RECORDS,
    ExecutionJournal,
    ExecutionRecord,
    FileExecutionJournal,
    InMemoryExecutionJournal,
)
from .autonomy.retrieval import (
    ChunkingPolicy,
    Document,
    DocumentChunk,
    EmbeddingProvider,
    InMemoryLexicalRetriever,
    InMemoryVectorRetriever,
    RetrievalBackend,
    RetrievalHit,
    SourceRef,
    TextChunker,
    VectorRetrievalHit,
)
from .autonomy.runs import (
    DEFAULT_MAX_RUN_BYTES,
    DEFAULT_MAX_RUN_MESSAGES,
    DEFAULT_MAX_RUN_TRACE,
    AgentRunCheckpoint,
    AgentRunStore,
    FileAgentRunStore,
    InMemoryAgentRunStore,
)
from .autonomy.server import RunServer, WorkflowRegistry
from .autonomy.sessions import (
    DEFAULT_MAX_MESSAGE_BYTES,
    DEFAULT_MAX_MESSAGES,
    DEFAULT_MAX_METADATA_BYTES,
    DEFAULT_MAX_SESSION_BYTES,
    DEFAULT_MAX_SESSIONS,
    FileSessionStore,
    InMemorySessionStore,
    SessionMessage,
    SessionSnapshot,
    SessionStore,
)
from .autonomy.tools import Tool, ToolRegistry, create_handoff_tool
from .autonomy.workflow import (
    END,
    CheckpointStore,
    FileCheckpointStore,
    HistoryCheckpointStore,
    InMemoryCheckpointStore,
    Workflow,
    WorkflowCheckpoint,
    WorkflowContext,
    WorkflowPause,
    WorkflowRun,
    RetryPolicy,
)
from .broker.broker import MessageBroker
from .communication.streaming import Stream, StreamOptions
from .core.message import Message, Priority
from .core.result import Result
from .core.types import AgentID, Duration, MessageID, Size
from .error.circuit_breaker import CircuitBreaker
from .error.recovery import RetryOptions, exponential_backoff, retry
from .error.types import Error, ErrorType, Severity
from .llm.capabilities import (
    ProviderCapabilities,
    ProviderDescriptor,
    ProviderRequirements,
    ProviderRouter,
)
from .llm.registry import LLMProviderRegistry
from .llm.types import ChatMessage, ChatRole, LLMConfig
from .resources.lease import Lease, LeaseManager
from .resources.manager import (
    DEFAULT_LIFECYCLES,
    ResourceAllocation,
    ResourceLifecycle,
    ResourceManager,
)
from .resources.negotiation import ResourceNegotiator
from .resources.specification import ResourceRange, ResourceRequest, TimeConstraint

# S2.dev durable streaming integration (optional)
try:
    from .adapters.s2_adapter import S2Broker, S2Config, S2StateBackend  # noqa: F401
except ImportError:  # pragma: no cover
    pass

__version__ = "1.1.3"
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
    "ResourceLifecycle",
    "DEFAULT_LIFECYCLES",
    "ResourceNegotiator",
    "Lease",
    "LeaseManager",
    # Communication patterns
    "Stream",
    "StreamOptions",
    # Autonomy layer
    "AutonomousAgent",
    "AutonomousConfig",
    "Goal",
    "Tool",
    "ToolRegistry",
    "create_handoff_tool",
    "MemoryManager",
    "AgentOrchestrator",
    "END",
    "CheckpointStore",
    "FileCheckpointStore",
    "HistoryCheckpointStore",
    "InMemoryCheckpointStore",
    "Workflow",
    "WorkflowCheckpoint",
    "WorkflowContext",
    "WorkflowPause",
    "WorkflowRun",
    "RetryPolicy",
    "Guardrail",
    "parse_structured_output",
    "parse_typed_output",
    "run_guardrails",
    "schema_guardrail",
    "structured_model_schema",
    "validate_json_schema",
    "validate_typed_value",
    "CancellationToken",
    "ExecutionExecutor",
    "ExecutionPolicy",
    "TrustedLocalExecutor",
    "ChunkingPolicy",
    "Document",
    "DocumentChunk",
    "EmbeddingProvider",
    "InMemoryLexicalRetriever",
    "InMemoryVectorRetriever",
    "RetrievalBackend",
    "RetrievalHit",
    "SourceRef",
    "TextChunker",
    "VectorRetrievalHit",
    "DEFAULT_MAX_RUN_BYTES",
    "DEFAULT_MAX_RUN_MESSAGES",
    "DEFAULT_MAX_RUN_TRACE",
    "AgentRunCheckpoint",
    "AgentRunStore",
    "FileAgentRunStore",
    "InMemoryAgentRunStore",
    "AgentEvent",
    "EventBatch",
    "EventCursor",
    "EventExporter",
    "EventStream",
    "RedactionPolicy",
    "HumanInputDecision",
    "HumanInputNotification",
    "HumanInputNotifier",
    "HumanInputAuthorizer",
    "HumanInputRound",
    "HumanInputRequest",
    "HumanInputStore",
    "FileHumanInputStore",
    "InMemoryHumanInputStore",
    "EvalCase",
    "EvalJudge",
    "EvalJudgeResult",
    "EvalObservation",
    "EvalReport",
    "EvalResult",
    "EvaluationHarness",
    "GroundednessEvalCase",
    "GroundednessObservation",
    "GroundingSource",
    "RetrievalEvalCase",
    "InteropEnvelope",
    "round_trip_json",
    "HandoffRecord",
    "HandoffStore",
    "FileHandoffStore",
    "InMemoryHandoffStore",
    "Artifact",
    "ArtifactStore",
    "CodeBlock",
    "FileArtifactStore",
    "InMemoryArtifactStore",
    "extract_code_blocks",
    "ApprovalDecision",
    "ApprovalRequest",
    "ApprovalStore",
    "FileApprovalStore",
    "InMemoryApprovalStore",
    "DEFAULT_MAX_MESSAGES",
    "DEFAULT_MAX_MESSAGE_BYTES",
    "DEFAULT_MAX_METADATA_BYTES",
    "DEFAULT_MAX_SESSION_BYTES",
    "DEFAULT_MAX_SESSIONS",
    "FileSessionStore",
    "InMemorySessionStore",
    "SessionMessage",
    "SessionSnapshot",
    "SessionStore",
    "RunServer",
    "WorkflowRegistry",
    "DEFAULT_MAX_RECORD_BYTES",
    "DEFAULT_MAX_RECORDS",
    "DEFAULT_MAX_RUN_RECORDS",
    "ExecutionJournal",
    "ExecutionRecord",
    "FileExecutionJournal",
    "InMemoryExecutionJournal",
    "LLMConfig",
    "ChatMessage",
    "ChatRole",
    "LLMProviderRegistry",
    "ProviderCapabilities",
    "ProviderDescriptor",
    "ProviderRequirements",
    "ProviderRouter",
    # S2.dev integration (optional)
    "S2Broker",
    "S2StateBackend",
    "S2Config",
    # Package metadata
    "__version__",
    "__author__",
    "__license__",
]


# Validation that our perfect test score is maintained
def validate_installation() -> Dict[str, Any]:
    """Validate that MAPLE is properly installed and ready to use."""
    try:
        # Test core functionality
        config = Config(agent_id="validation_test", broker_url="memory://test")
        Agent(config)

        Message(message_type="VALIDATION_TEST", payload={"test": True})

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
def print_banner() -> None:
    """Print MAPLE banner."""
    print(
        f"""
MAPLE v{__version__} - Multi Agent Protocol Language Engine

Created by: {__author__}
License: {__license__}
"""
    )
