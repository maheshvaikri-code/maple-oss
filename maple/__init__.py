"""
Copyright (C) 2025 Mahesh Vaijainthymala Krishnamoorthy
(Mahesh Vaikri)

This file is part of MAPLE - Multi Agent Protocol Language Engine.

MAPLE - Multi Agent Protocol Language Engine is free software: you can
redistribute it and/or modify it under the terms of the GNU Affero General
Public License as published by the Free Software Foundation, either version 3
of the License, or (at your option) any later version.
MAPLE - Multi Agent Protocol Language Engine is distributed in the hope that
it will be useful, but WITHOUT ANY WARRANTY; without even the implied warranty
of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU Affero
General Public License for more details. You should have received a copy of
the GNU Affero General Public License along with MAPLE - Multi Agent Protocol
Language Engine. If not, see <https://www.gnu.org/licenses/>.
"""

# MAPLE - Multi Agent Protocol Language Engine.
# Created by: Mahesh Vaijainthymala Krishnamoorthy (Mahesh Vaikri).
# Multi-agent communication protocol with advanced resource management,
# type-safe Result<T,E> error handling, link identification security, and
# multi-agent communication.

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
from .autonomy.agent_transport import AutonomousAgentRemoteAdapter
from .autonomy.approval import (
    ApprovalDecision,
    ApprovalNotification,
    ApprovalNotifier,
    ApprovalRequest,
    ApprovalStore,
    FileApprovalNotificationOutbox,
    FileApprovalStore,
    HttpApprovalNotifier,
    InMemoryApprovalStore,
)
from .autonomy.artifacts import (
    Artifact,
    ArtifactStore,
    CodeBlock,
    FileArtifactStore,
    InMemoryArtifactStore,
    extract_code_blocks,
    materialize_code_block,
)
from .autonomy.contracts import (
    Guardrail,
    GuardrailEvent,
    GuardrailObserver,
    parse_structured_output,
    parse_typed_output,
    run_guardrails,
    schema_guardrail,
    structured_model_schema,
    validate_json_schema,
    validate_typed_value,
)
from .autonomy.evaluation import (
    AsyncEvalJudge,
    EvalCalibrationCase,
    EvalCalibrationReport,
    EvalCalibrationResult,
    EvalCase,
    EvalJudge,
    EvalJudgeResult,
    EvalObservation,
    EvalReport,
    EvalResult,
    EvalTrajectoryStep,
    EvaluationHarness,
    GroundednessEvalCase,
    GroundednessObservation,
    GroundingSource,
    RetrievalEvalCase,
    TraceEvalCase,
    TraceEvalSpan,
)
from .autonomy.events import (
    DEFAULT_EVENT_DEDUP_TTL_SECONDS,
    DEFAULT_FORWARD_INTERVAL_SECONDS,
    DEFAULT_MAX_CURSOR_BYTES,
    DEFAULT_MAX_EVENT_DEDUP_BYTES,
    DEFAULT_MAX_EVENT_DEDUP_ENTRIES,
    DEFAULT_MAX_FORWARD_BATCH_ITEMS,
    DEFAULT_MAX_FORWARD_BATCHES_PER_TICK,
    DEFAULT_MAX_JOURNAL_BYTES,
    AgentEvent,
    EventBatch,
    EventBatchSender,
    EventCursor,
    EventCursorStore,
    EventDeduplicationStore,
    EventDelivery,
    EventDeliveryFailure,
    EventExporter,
    EventForwarder,
    EventForwarderScheduler,
    EventForwarderSchedulerStats,
    EventForwardReport,
    EventJournal,
    EventStream,
    FileEventCursorStore,
    FileEventDeduplicationStore,
    FileEventJournal,
    HttpEventBatchSender,
    HttpEventExporter,
    InMemoryEventCursorStore,
    InMemoryEventDeduplicationStore,
    RedactionPolicy,
    validate_event_source_id,
)
from .autonomy.execution import (
    CancellationToken,
    ExecutionExecutor,
    ExecutionPolicy,
    TrustedLocalExecutor,
)
from .autonomy.handoffs import (
    FileHandoffStore,
    HandoffRecord,
    HandoffStore,
    InMemoryHandoffStore,
)
from .autonomy.interactions import (
    FileHumanInputNotificationOutbox,
    FileHumanInputStore,
    HttpHumanInputNotifier,
    HumanInputAuthorizer,
    HumanInputDecision,
    HumanInputNotification,
    HumanInputNotifier,
    HumanInputRequest,
    HumanInputRound,
    HumanInputStore,
    InMemoryHumanInputStore,
)
from .autonomy.interop import InteropEnvelope, round_trip_json
from .autonomy.invocations import (
    DEFAULT_AGENT_INVOCATION_TTL_SECONDS,
    DEFAULT_MAX_AGENT_INVOCATION_BYTES,
    DEFAULT_MAX_AGENT_INVOCATION_ENTRIES,
    DEFAULT_MAX_AGENT_INVOCATION_RESPONSE_BYTES,
    AgentInvocationDeduplicationStore,
    AgentInvocationResponse,
    FileAgentInvocationDeduplicationStore,
    InMemoryAgentInvocationDeduplicationStore,
    fingerprint_agent_invocation,
    normalize_agent_idempotency_key,
)
from .autonomy.memory import MemoryManager
from .autonomy.notification_outbox import (
    DEFAULT_MAX_NOTIFICATION_OUTBOX_BYTES,
    DEFAULT_MAX_NOTIFICATION_OUTBOX_DRAIN,
    DEFAULT_MAX_NOTIFICATION_OUTBOX_RECORD_BYTES,
    DEFAULT_MAX_NOTIFICATION_OUTBOX_RECORDS,
    DEFAULT_NOTIFICATION_OUTBOX_DRAIN_LEASE_TTL_SECONDS,
    FileNotificationOutbox,
    NotificationOutboxReport,
    NotificationOutboxTarget,
)
from .autonomy.observability import SpanRecorder, TraceSpan
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
    DEFAULT_MAX_RETRIEVAL_TOOL_OUTPUT_BYTES,
    DEFAULT_MAX_RETRIEVAL_TOOL_RESULTS,
    AsyncDocumentConnector,
    AsyncEmbeddingProvider,
    ChunkingPolicy,
    ConnectorIngestReport,
    Document,
    DocumentBatch,
    DocumentChunk,
    DocumentConnector,
    DocumentConnectorRateLimiter,
    DocumentCursorCheckpoint,
    DocumentCursorCheckpointStore,
    DocumentIngestor,
    EmbeddingProvider,
    FileDocumentCursorCheckpointStore,
    FileLexicalRetriever,
    FileVectorRetriever,
    InMemoryDocumentConnectorRateLimiter,
    InMemoryDocumentCursorCheckpointStore,
    InMemoryLexicalRetriever,
    InMemoryVectorRetriever,
    RerankedRetrievalHit,
    RetrievalBackend,
    RetrievalHit,
    RetrievalReranker,
    SourceRef,
    TextChunker,
    VectorRetrievalHit,
    create_async_vector_retrieval_tool,
    create_retrieval_tool,
    create_vector_retrieval_tool,
    ingest_documents,
    ingest_documents_async,
    rerank_hits,
)
from .autonomy.runs import (
    DEFAULT_MAX_RUN_BYTES,
    DEFAULT_MAX_RUN_HISTORY,
    DEFAULT_MAX_RUN_MESSAGES,
    DEFAULT_MAX_RUN_TRACE,
    AgentRunCheckpoint,
    AgentRunHistoryStore,
    AgentRunStore,
    FileAgentRunStore,
    InMemoryAgentRunStore,
)
from .autonomy.server import (
    AgentDescriptor,
    AgentRegistry,
    AgentRun,
    AgentRunCancelHandler,
    AgentRunHandler,
    AgentRunResumeHandler,
    AuthPrincipalResolver,
    Principal,
    RemoteHandoffResult,
    RemoteHandoffTarget,
    RunClient,
    RunServer,
    WorkflowRegistry,
)
from .autonomy.sessions import (
    DEFAULT_MAX_HISTORY,
    DEFAULT_MAX_MESSAGE_BYTES,
    DEFAULT_MAX_MESSAGES,
    DEFAULT_MAX_METADATA_BYTES,
    DEFAULT_MAX_SESSION_BYTES,
    DEFAULT_MAX_SESSIONS,
    MAX_HISTORY,
    FileSessionStore,
    InMemorySessionStore,
    SessionCompactionStore,
    SessionMessage,
    SessionSnapshot,
    SessionStore,
)
from .autonomy.tools import (
    TOOL_REPLAY_DISABLED,
    TOOL_REPLAY_REUSE_SUCCESS,
    Tool,
    ToolRegistry,
    create_agent_tool,
    create_handoff_tool,
)
from .autonomy.workflow import (
    END,
    CheckpointStore,
    FileCheckpointStore,
    HistoryCheckpointStore,
    InMemoryCheckpointStore,
    RetryPolicy,
    Workflow,
    WorkflowCheckpoint,
    WorkflowContext,
    WorkflowPause,
    WorkflowRun,
)
from .broker.broker import MessageBroker
from .communication.streaming import Stream, StreamOptions
from .core.message import Message, Priority
from .core.result import Result, UnwrapError
from .core.types import AgentID, Duration, MessageID, Size
from .error.circuit_breaker import CircuitBreaker
from .error.recovery import RetryOptions, exponential_backoff, retry
from .error.types import (
    BrokerOverflowError,
    BrokerUnavailableError,
    Error,
    ErrorType,
    SecurityError,
    Severity,
)
from .llm.capabilities import (
    FallbackLLMProvider,
    ProviderCapabilities,
    ProviderDescriptor,
    ProviderRequirements,
    ProviderRouter,
)
from .llm.registry import LLMProviderRegistry
from .llm.types import (
    ChatContent,
    ChatMessage,
    ChatRole,
    ContentPart,
    ImageContent,
    LLMConfig,
    ModelRetryPolicy,
    validate_chat_content,
)
from .monitoring.health_monitor import (
    ComponentHealthMetrics,
    ComponentHealthMonitor,
)
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

__version__ = "2.1.0"
__author__ = "Mahesh Vaijainthymala Krishnamoorthy (Mahesh Vaikri)"
__email__ = "mahesh@mapleagent.org"
__license__ = "AGPL 3.0"

# Package metadata
__status__ = "Active Development"

__title__ = "maple"
__description__ = (
    "Multi Agent Protocol Language Engine - Advanced Multi-Agent "
    "Communication Protocol Framework"
)
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
    "SecurityError",
    "BrokerUnavailableError",
    "BrokerOverflowError",
    "UnwrapError",
    "ComponentHealthMonitor",
    "ComponentHealthMetrics",
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
    "TOOL_REPLAY_DISABLED",
    "TOOL_REPLAY_REUSE_SUCCESS",
    "create_agent_tool",
    "create_handoff_tool",
    "MemoryManager",
    "SpanRecorder",
    "TraceSpan",
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
    "GuardrailEvent",
    "GuardrailObserver",
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
    "AsyncDocumentConnector",
    "AsyncEmbeddingProvider",
    "ChunkingPolicy",
    "ConnectorIngestReport",
    "DEFAULT_MAX_RETRIEVAL_TOOL_OUTPUT_BYTES",
    "DEFAULT_MAX_RETRIEVAL_TOOL_RESULTS",
    "Document",
    "DocumentBatch",
    "DocumentChunk",
    "DocumentConnector",
    "DocumentConnectorRateLimiter",
    "DocumentCursorCheckpoint",
    "DocumentCursorCheckpointStore",
    "DocumentIngestor",
    "EmbeddingProvider",
    "FileDocumentCursorCheckpointStore",
    "FileLexicalRetriever",
    "FileVectorRetriever",
    "InMemoryDocumentCursorCheckpointStore",
    "InMemoryDocumentConnectorRateLimiter",
    "InMemoryLexicalRetriever",
    "InMemoryVectorRetriever",
    "RetrievalBackend",
    "RetrievalHit",
    "RetrievalReranker",
    "RerankedRetrievalHit",
    "SourceRef",
    "TextChunker",
    "VectorRetrievalHit",
    "create_async_vector_retrieval_tool",
    "create_retrieval_tool",
    "create_vector_retrieval_tool",
    "ingest_documents_async",
    "ingest_documents",
    "rerank_hits",
    "DEFAULT_MAX_RUN_BYTES",
    "DEFAULT_MAX_RUN_HISTORY",
    "DEFAULT_MAX_RUN_MESSAGES",
    "DEFAULT_MAX_RUN_TRACE",
    "AgentRunCheckpoint",
    "AgentRunHistoryStore",
    "AgentRunStore",
    "FileAgentRunStore",
    "InMemoryAgentRunStore",
    "AgentEvent",
    "DEFAULT_MAX_EVENT_DEDUP_BYTES",
    "DEFAULT_MAX_CURSOR_BYTES",
    "DEFAULT_MAX_EVENT_DEDUP_ENTRIES",
    "DEFAULT_EVENT_DEDUP_TTL_SECONDS",
    "DEFAULT_MAX_FORWARD_BATCH_ITEMS",
    "DEFAULT_FORWARD_INTERVAL_SECONDS",
    "DEFAULT_MAX_FORWARD_BATCHES_PER_TICK",
    "DEFAULT_MAX_JOURNAL_BYTES",
    "EventBatch",
    "EventBatchSender",
    "EventCursor",
    "EventCursorStore",
    "EventDeduplicationStore",
    "EventDelivery",
    "EventDeliveryFailure",
    "EventExporter",
    "EventForwardReport",
    "EventForwarderScheduler",
    "EventForwarderSchedulerStats",
    "EventForwarder",
    "EventJournal",
    "FileEventCursorStore",
    "FileEventDeduplicationStore",
    "EventStream",
    "FileEventJournal",
    "HttpEventBatchSender",
    "HttpEventExporter",
    "InMemoryEventCursorStore",
    "InMemoryEventDeduplicationStore",
    "RedactionPolicy",
    "validate_event_source_id",
    "HumanInputDecision",
    "HumanInputNotification",
    "HumanInputNotifier",
    "HttpHumanInputNotifier",
    "HumanInputAuthorizer",
    "HumanInputRound",
    "HumanInputRequest",
    "HumanInputStore",
    "FileHumanInputStore",
    "FileHumanInputNotificationOutbox",
    "InMemoryHumanInputStore",
    "DEFAULT_MAX_NOTIFICATION_OUTBOX_BYTES",
    "DEFAULT_MAX_NOTIFICATION_OUTBOX_DRAIN",
    "DEFAULT_MAX_NOTIFICATION_OUTBOX_RECORD_BYTES",
    "DEFAULT_MAX_NOTIFICATION_OUTBOX_RECORDS",
    "DEFAULT_NOTIFICATION_OUTBOX_DRAIN_LEASE_TTL_SECONDS",
    "FileNotificationOutbox",
    "NotificationOutboxReport",
    "NotificationOutboxTarget",
    "DEFAULT_AGENT_INVOCATION_TTL_SECONDS",
    "DEFAULT_MAX_AGENT_INVOCATION_BYTES",
    "DEFAULT_MAX_AGENT_INVOCATION_ENTRIES",
    "DEFAULT_MAX_AGENT_INVOCATION_RESPONSE_BYTES",
    "AgentInvocationDeduplicationStore",
    "AgentInvocationResponse",
    "FileAgentInvocationDeduplicationStore",
    "InMemoryAgentInvocationDeduplicationStore",
    "fingerprint_agent_invocation",
    "normalize_agent_idempotency_key",
    "EvalCase",
    "EvalCalibrationCase",
    "EvalCalibrationReport",
    "EvalCalibrationResult",
    "AsyncEvalJudge",
    "EvalJudge",
    "EvalJudgeResult",
    "EvalObservation",
    "EvalReport",
    "EvalResult",
    "EvalTrajectoryStep",
    "EvaluationHarness",
    "GroundednessEvalCase",
    "GroundednessObservation",
    "GroundingSource",
    "RetrievalEvalCase",
    "TraceEvalCase",
    "TraceEvalSpan",
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
    "materialize_code_block",
    "ApprovalDecision",
    "ApprovalNotification",
    "ApprovalNotifier",
    "ApprovalRequest",
    "ApprovalStore",
    "FileApprovalNotificationOutbox",
    "FileApprovalStore",
    "HttpApprovalNotifier",
    "InMemoryApprovalStore",
    "DEFAULT_MAX_MESSAGES",
    "DEFAULT_MAX_HISTORY",
    "DEFAULT_MAX_MESSAGE_BYTES",
    "DEFAULT_MAX_METADATA_BYTES",
    "DEFAULT_MAX_SESSION_BYTES",
    "DEFAULT_MAX_SESSIONS",
    "FileSessionStore",
    "InMemorySessionStore",
    "MAX_HISTORY",
    "SessionCompactionStore",
    "SessionMessage",
    "SessionSnapshot",
    "SessionStore",
    "RunServer",
    "RunClient",
    "AuthPrincipalResolver",
    "WorkflowRegistry",
    "AgentRegistry",
    "AgentDescriptor",
    "AgentRun",
    "AgentRunHandler",
    "AgentRunCancelHandler",
    "AgentRunResumeHandler",
    "Principal",
    "RemoteHandoffResult",
    "RemoteHandoffTarget",
    "AutonomousAgentRemoteAdapter",
    "DEFAULT_MAX_RECORD_BYTES",
    "DEFAULT_MAX_RECORDS",
    "DEFAULT_MAX_RUN_RECORDS",
    "ExecutionJournal",
    "ExecutionRecord",
    "FileExecutionJournal",
    "InMemoryExecutionJournal",
    "LLMConfig",
    "ModelRetryPolicy",
    "ChatMessage",
    "ChatRole",
    "ChatContent",
    "ContentPart",
    "ImageContent",
    "validate_chat_content",
    "LLMProviderRegistry",
    "ProviderCapabilities",
    "ProviderDescriptor",
    "ProviderRequirements",
    "ProviderRouter",
    "FallbackLLMProvider",
    # S2.dev integration (optional)
    "S2Broker",
    "S2StateBackend",
    "S2Config",
    # Package metadata
    "__version__",
    "__author__",
    "__license__",
]


def validate_installation() -> Dict[str, Any]:
    """Check that MAPLE's core types are importable and usable.

    Deliberately free of side effects: it does **not** construct an ``Agent``.
    ``MessageBroker`` is a process-wide singleton that freezes its
    configuration at first construction, so building an agent here would pin
    the broker to this function's throwaway config and silently discard the
    configuration of every agent the caller creates afterwards. See ADR-157.
    """
    try:
        config = Config(agent_id="validation_test", broker_url="memory://test")
        message = Message(message_type="VALIDATION_TEST", payload={"test": True})

        # Exercise the pieces that carry the protocol: typed config, a
        # round-trippable message, and the Result contract every API returns.
        checked = (
            config.agent_id == "validation_test"
            and message.message_type == "VALIDATION_TEST"
            and Result.ok(True).unwrap() is True
            and Result.err("e").is_err()
        )
        if not checked:
            return {
                "status": "ERROR",
                "error": "core type invariants did not hold",
                "ready": False,
            }

        return {
            "status": "SUCCESS",
            "version": __version__,
            "ready": True,
        }

    except Exception as e:
        return {"status": "ERROR", "error": str(e), "ready": False}


# Package banner for CLI tools
def print_banner() -> None:
    """Print MAPLE banner."""
    banner = f"""
MAPLE v{__version__} - Multi Agent Protocol Language Engine

Created by: {__author__}
License: {__license__}
"""
    print(banner)
