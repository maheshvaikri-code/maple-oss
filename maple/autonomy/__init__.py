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

"""MAPLE Autonomy Layer - Autonomous agentic AI capabilities."""

from .tools import Tool, ToolRegistry
from .memory import WorkingMemory, EpisodicMemory, SemanticMemory, MemoryManager
from .agent import AutonomousAgent, AutonomousConfig, Goal, ReasoningStep
from .orchestrator import AgentOrchestrator, TeamMember
from .observability import DecisionTrace, DecisionLogger, AgentSnapshot
from .mcp_tools import discover_mcp_tools, register_mcp_tools
from .contracts import (
    Guardrail,
    parse_structured_output,
    run_guardrails,
    schema_guardrail,
    validate_json_schema,
)
from .execution import (
    CancellationToken,
    ExecutionExecutor,
    ExecutionPolicy,
    TrustedLocalExecutor,
)
from .retrieval import (
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
from .events import AgentEvent, EventStream, RedactionPolicy
from .evaluation import (
    EvalCase,
    EvalObservation,
    EvalReport,
    EvalResult,
    EvaluationHarness,
    RetrievalEvalCase,
)
from .interop import InteropEnvelope, round_trip_json
from .artifacts import (
    Artifact,
    ArtifactStore,
    CodeBlock,
    FileArtifactStore,
    InMemoryArtifactStore,
    extract_code_blocks,
)
from .approval import (
    ApprovalDecision,
    ApprovalRequest,
    ApprovalStore,
    FileApprovalStore,
    InMemoryApprovalStore,
)
from .workflow import (
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
)
from .sessions import (
    DEFAULT_MAX_MESSAGES,
    DEFAULT_MAX_MESSAGE_BYTES,
    DEFAULT_MAX_METADATA_BYTES,
    DEFAULT_MAX_SESSION_BYTES,
    DEFAULT_MAX_SESSIONS,
    FileSessionStore,
    InMemorySessionStore,
    SessionMessage,
    SessionSnapshot,
    SessionStore,
)
from .server import RunServer, WorkflowRegistry

__all__ = [
    "Tool",
    "ToolRegistry",
    "WorkingMemory",
    "EpisodicMemory",
    "SemanticMemory",
    "MemoryManager",
    "AutonomousAgent",
    "AutonomousConfig",
    "Goal",
    "ReasoningStep",
    "AgentOrchestrator",
    "TeamMember",
    "DecisionTrace",
    "DecisionLogger",
    "AgentSnapshot",
    "discover_mcp_tools",
    "register_mcp_tools",
    "Guardrail",
    "parse_structured_output",
    "run_guardrails",
    "schema_guardrail",
    "validate_json_schema",
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
    "AgentEvent",
    "EventStream",
    "RedactionPolicy",
    "EvalCase",
    "EvalObservation",
    "EvalReport",
    "EvalResult",
    "EvaluationHarness",
    "RetrievalEvalCase",
    "InteropEnvelope",
    "round_trip_json",
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
]
