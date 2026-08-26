# API Reference - MAPLE

**Creator: Mahesh Vaijainthymala Krishnamoorthy (Mahesh Vaikri)**

API reference for MAPLE (Multi Agent Protocol Language Engine).

## Core Classes

### Agent Class

The central class for creating and managing agents.

```python
class Agent:
    def __init__(self, config: Config, broker: Optional[MessageBroker] = None):
        """
        Initialize agent with configuration.

        Args:
            config (Config): Agent configuration including security and resources
            broker (MessageBroker, optional): Custom broker instance
        """
```

#### Methods

##### Core Communication

```python
def start(self) -> None:
    """Start the agent and establish broker connections."""

def stop(self) -> None:
    """Stop the agent and clean up connections."""

def send(self, message: Message) -> Result[str, Dict[str, Any]]:
    """
    Send a message with Result<T,E> error handling.

    Args:
        message (Message): Message to send

    Returns:
        Result[str, Dict]: Success with message_id or detailed error
    """

def request(self, message: Message, timeout: str = "30s") -> Result[Message, Dict[str, Any]]:
    """
    Send message and wait for response with timeout.

    Args:
        message (Message): Request message
        timeout (str): Timeout duration (e.g., "30s", "5m")

    Returns:
        Result[Message, Dict]: Response message or timeout error
    """

def receive(self, timeout: Optional[str] = None) -> Result[Message, Dict[str, Any]]:
    """
    Receive a message from the agent's queue.

    Args:
        timeout (str, optional): Timeout duration

    Returns:
        Result[Message, Dict]: Received message or timeout/error
    """

def broadcast(self, recipients: List[str], message: Message) -> Dict[str, Result[str, Dict[str, Any]]]:
    """
    Send a message to multiple recipients.

    Args:
        recipients: List of agent IDs
        message: Message to broadcast

    Returns:
        Dict mapping agent_id to send Result
    """
```

##### Pub/Sub Communication

```python
def publish(self, topic: str, message: Message) -> Result[str, Dict[str, Any]]:
    """Publish a message to a topic."""

def subscribe(self, topic: str) -> Result[None, Dict[str, Any]]:
    """Subscribe to a topic."""
```

##### Secure Communication (Link Identification)

```python
def establish_link(
    self,
    agent_id: str,
    lifetime_seconds: int = 3600
) -> Result[str, Dict[str, Any]]:
    """
    Establish a cryptographically verified secure communication link.

    Args:
        agent_id (str): Target agent identifier
        lifetime_seconds (int): Link validity duration

    Returns:
        Result with link_id or establishment failure details
    """

def send_with_link(
    self,
    message: Message,
    agent_id: str
) -> Result[str, Dict[str, Any]]:
    """
    Send message through an established secure link.

    Args:
        message (Message): Message to send (should have link via .with_link())
        agent_id (str): Target agent identifier

    Returns:
        Result with message_id or link validation error
    """
```

##### Handler Registration

```python
def register_handler(
    self,
    message_type: str,
    handler: Callable[[Message], Optional[Message]]
) -> None:
    """Register handler for a specific message type."""

def register_topic_handler(
    self,
    topic: str,
    handler: Callable[[Message], Optional[Message]]
) -> None:
    """Register handler for a topic."""

# Decorator forms
@agent.handler("MESSAGE_TYPE")
def handle_message(message: Message) -> Optional[Message]:
    """Decorator for registering message handlers."""

@agent.topic_handler("topic_name")
def handle_topic(message: Message) -> Optional[Message]:
    """Decorator for registering topic handlers."""
```

##### Streaming

```python
def create_stream(self, name: str) -> Result[Stream, Dict[str, Any]]:
    """Create a new message stream."""

def connect_stream(self, name: str) -> Result[Stream, Dict[str, Any]]:
    """Connect to an existing message stream."""

@agent.stream_handler("stream_name")
def handle_stream(message: Message) -> None:
    """Decorator for registering stream handlers."""
```

### Message Class

```python
class Message:
    def __init__(
        self,
        message_type: str,
        receiver: Optional[str] = None,
        priority: Priority = Priority.MEDIUM,
        payload: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        message_id: Optional[str] = None,
        sender: Optional[str] = None,
        timestamp: Optional[datetime] = None
    ):
```

#### Message Methods

```python
def with_link(self, link_id: str) -> 'Message':
    """Associate message with a secure link."""

def with_receiver(self, receiver: str) -> 'Message':
    """Set the message receiver."""

def get_link_id(self) -> Optional[str]:
    """Get the associated link ID, if any."""

def add_metadata(self, key: str, value: Any) -> None:
    """Add metadata to the message."""

def get_metadata(self, key: str, default: Any = None) -> Any:
    """Get metadata by key."""

def to_dict(self) -> Dict[str, Any]:
    """Serialize to dictionary."""

def to_json(self) -> str:
    """Serialize to JSON string."""

@classmethod
def from_dict(cls, data: Dict[str, Any]) -> 'Message':
    """Deserialize from dictionary."""

@classmethod
def from_json(cls, json_str: str) -> 'Message':
    """Deserialize from JSON string."""

@classmethod
def error(
    cls,
    error_type: str,
    message: str,
    details: Optional[Dict[str, Any]] = None,
    severity: str = "HIGH",
    recoverable: bool = False,
    receiver: Optional[str] = None,
    correlation_id: Optional[str] = None
) -> 'Message':
    """Create a structured error message."""

@classmethod
def ack(cls, correlation_id: str, receiver: Optional[str] = None) -> 'Message':
    """Create an acknowledgement message."""

def builder() -> 'Message.Builder':
    """Get a builder for fluent message construction."""
```

### Result\<T,E\> Type

Rust-inspired type-safe error handling.

```python
class Result[T, E]:
    @classmethod
    def ok(cls, value: T) -> 'Result[T, E]':
        """Create successful result."""

    @classmethod
    def err(cls, error: E) -> 'Result[T, E]':
        """Create error result."""

    def is_ok(self) -> bool:
        """Check if result is successful."""

    def is_err(self) -> bool:
        """Check if result contains error."""

    def unwrap(self) -> T:
        """Extract success value. Raises if Err."""

    def unwrap_or(self, default: T) -> T:
        """Extract success value or return default."""

    def unwrap_err(self) -> E:
        """Extract error value. Raises if Ok."""

    def map(self, f: Callable[[T], U]) -> 'Result[U, E]':
        """Transform success value."""

    def map_err(self, f: Callable[[E], F]) -> 'Result[T, F]':
        """Transform error value."""

    def and_then(self, f: Callable[[T], 'Result[U, E]']) -> 'Result[U, E]':
        """Chain operations with automatic error propagation."""

    def or_else(self, f: Callable[[E], 'Result[T, F]']) -> 'Result[T, F]':
        """Provide error recovery alternative."""

    def to_dict(self) -> dict:
        """Serialize to dictionary."""

    @classmethod
    def from_dict(cls, data: dict) -> 'Result[Any, Any]':
        """Deserialize from dictionary."""
```

## Serialization Formats

`Serializer` supports JSON, restricted Pickle, optional MessagePack, and
optional bounded Protobuf envelopes. Protobuf uses a `google.protobuf.Struct`
envelope around MAPLE's JSON-compatible representation, preserving MAPLE's
tuple, set, bytes, and inert-object handling without reconstructing arbitrary
classes. Protobuf input and output are capped at 1 MiB; installations without
the optional library return `PROTOBUF_UNAVAILABLE`.

```python
from maple.core.serialization import SerializationFormat, Serializer

serializer = Serializer()
encoded = serializer.serialize(
    {"request_id": "r-1", "attempt": 2}, SerializationFormat.PROTOBUF
)
if encoded.is_ok():
    decoded = serializer.deserialize(
        encoded.unwrap(), SerializationFormat.PROTOBUF
    )
```

## Resource Management

### ResourceRequest Class

```python
@dataclass
class ResourceRequest:
    compute: Optional[ResourceRange] = None
    memory: Optional[ResourceRange] = None
    bandwidth: Optional[ResourceRange] = None
    time: Optional[TimeConstraint] = None
    priority: str = "MEDIUM"

    def to_dict(self) -> Dict[str, Any]: ...

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ResourceRequest': ...
```

### ResourceRange Class

```python
@dataclass
class ResourceRange:
    min: Any
    preferred: Optional[Any] = None
    max: Optional[Any] = None
```

### ResourceManager Class

```python
class ResourceManager:
    def allocate_resources(
        self,
        request: ResourceRequest
    ) -> Result[ResourceAllocation, Dict[str, Any]]:
        """Allocate resources based on request and availability."""

    def release_resources(self, allocation_id: str) -> Result[None, Dict[str, Any]]:
        """Release a previous allocation."""
```

## Security Framework

### LinkManager Class

```python
class LinkManager:
    def initiate_link(self, agent_a: str, agent_b: str) -> Link:
        """Initiate a new link between two agents."""

    def establish_link(
        self,
        link_id: str,
        lifetime_seconds: int = 3600
    ) -> Result[Link, Dict[str, Any]]:
        """Establish a previously initiated link."""

    def validate_link(
        self,
        link_id: str,
        sender: str,
        receiver: str
    ) -> Result[Link, Dict[str, Any]]:
        """Validate link authenticity and authorization."""

    def terminate_link(self, link_id: str) -> Result[None, Dict[str, Any]]:
        """Terminate an established link."""

    def get_links_for_agent(self, agent_id: str) -> Result[list, Dict[str, Any]]:
        """Get all links for a specific agent."""
```

### SecurityConfig Class

```python
@dataclass
class SecurityConfig:
    auth_type: str
    credentials: str
    public_key: Optional[str] = None
    private_key: Optional[str] = None
    permissions: Optional[List[Dict[str, Any]]] = None
    require_links: bool = False
    strict_link_policy: bool = False
    link_config: Optional[LinkConfig] = None
```

## State Management

### StateStore Class

```python
class StateStore:
    def __init__(
        self,
        backend: StorageBackend = StorageBackend.MEMORY,
        consistency: ConsistencyLevel = ConsistencyLevel.EVENTUAL,
        config: Optional[Dict[str, Any]] = None
    ):

    def get(self, key: str) -> Result[Optional[Any], Dict[str, Any]]:
        """Get state value by key."""

    def set(
        self,
        key: str,
        value: Any,
        metadata: Optional[Dict[str, Any]] = None,
        expected_version: Optional[int] = None
    ) -> Result[StateEntry, Dict[str, Any]]:
        """Set state value with optional version checking."""

    def delete(
        self,
        key: str,
        expected_version: Optional[int] = None
    ) -> Result[bool, Dict[str, Any]]:
        """Delete a state entry."""

    def list_keys(self, prefix: Optional[str] = None) -> Result[List[str], Dict[str, Any]]:
        """List state keys, optionally filtered by prefix."""

    def add_listener(self, listener: Callable[[str, StateEntry], None]) -> None:
        """Register a listener for state changes."""

    def remove_listener(self, listener: Callable[[str, StateEntry], None]) -> None:
        """Remove a state change listener."""

    def get_statistics(self) -> Dict[str, Any]:
        """Get store statistics."""
```

### Enums

```python
class StorageBackend(Enum):
    MEMORY = "memory"
    FILE = "file"
    REDIS = "redis"
    DATABASE = "database"

class ConsistencyLevel(Enum):
    EVENTUAL = "eventual"
    STRONG = "strong"
    CAUSAL = "causal"

class Priority(Enum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
```

## Configuration Classes

### Config Class

```python
@dataclass
class Config:
    agent_id: str
    broker_url: str
    security: Optional[SecurityConfig] = None
    performance: Optional[PerformanceConfig] = None
    metrics: Optional[MetricsConfig] = None
    tracing: Optional[TracingConfig] = None
```

## Error Handling

### Error Types

```python
class ErrorType(Enum):
    NETWORK_ERROR = "NETWORK_ERROR"
    TIMEOUT = "TIMEOUT"
    ROUTING_ERROR = "ROUTING_ERROR"
    MESSAGE_VALIDATION_ERROR = "MESSAGE_VALIDATION_ERROR"
    RESOURCE_UNAVAILABLE = "RESOURCE_UNAVAILABLE"
    RESOURCE_EXHAUSTED = "RESOURCE_EXHAUSTED"
    AUTHENTICATION_ERROR = "AUTHENTICATION_ERROR"
    AUTHORIZATION_ERROR = "AUTHORIZATION_ERROR"
    LINK_VERIFICATION_FAILED = "LINK_VERIFICATION_FAILED"
    ENCRYPTION_ERROR = "ENCRYPTION_ERROR"
    STATE_CONFLICT = "STATE_CONFLICT"
```

### Recovery Utilities

```python
def retry(
    operation: Callable,
    options: RetryOptions
) -> Result:
    """Retry an operation with configurable backoff."""

def exponential_backoff(attempt: int, base_delay: float = 1.0) -> float:
    """Calculate exponential backoff delay."""

class CircuitBreaker:
    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: float = 60.0,
        half_open_max_calls: int = 3
    ):
        """Circuit breaker pattern for preventing cascading failures."""
```

## Trusted Local Execution (preview)

`TrustedLocalExecutor` is an explicit boundary for trusted Python handlers. It
adds input/output byte limits, bounded concurrent workers, approval callbacks,
timeouts, and cooperative cancellation. A timeout sets the cancellation token
and returns a structured failure, but cannot forcibly kill a Python thread;
model-generated code, shell commands, and other untrusted execution require a
separately reviewed process or hosted sandbox and are not supported here.

```python
from maple import CancellationToken, ExecutionPolicy, TrustedLocalExecutor

token = CancellationToken()
executor = TrustedLocalExecutor(
    ExecutionPolicy(
        timeout_seconds=5,
        max_input_bytes=64_000,
        max_output_bytes=256_000,
        max_concurrent=4,
    )
)
result = executor.execute(
    "lookup",
    trusted_lookup,
    kwargs={"key": "example"},
    cancellation=token,
)
```

### Durable fencing leases

`LeaseManager` is the in-memory option. `FileLeaseManager` persists ownership
and fencing counters under a caller-owned directory and serializes each
read/modify/write operation across local processes with an OS file lock.

```python
from maple.resources import FileLeaseManager

leases = FileLeaseManager("./runtime/leases")
acquired = leases.acquire("robot-arm", "worker-a", ttl_seconds=60)
lease = acquired.unwrap()

# The guarded resource must check the current fencing token immediately before
# its side effect; a stale token cannot release a newer holder's lease.
assert leases.is_valid(lease)
leases.release(lease)
```

Resource and holder identifiers are bounded to 256 characters and TTLs are
bounded to seven days. State is atomically replaced after flush and fsync.
Mutating storage failures return typed `LEASE_STORAGE_ERROR` or
`LEASE_LOCK_TIMEOUT` results; inspection failures return false/empty values.
This primitive does not automatically own durable approval/input/run records,
provide remote authentication, or promise exactly-once external effects.

Pass the executor to `Tool(executor=...)` to apply the same boundary to a
tool. Handlers that need cancellation should close over the token and check
`token.is_cancelled()` or `token.wait()` while working.

## Typed Agent Contracts (preview)

MAPLE can validate tool inputs and outputs against a bounded JSON-Schema subset
or optional Pydantic-style models, parse structured model responses, and apply
synchronous guardrails at agent and tool boundaries. Guardrails may return
`True`/`None` to allow a value, `False` to reject it, or a `Result`. Exceptions
and malformed guardrail results fail closed. The validator enforces depth and
collection-size limits; regular expression `pattern` constraints are rejected
because they cannot be given a reliable execution deadline by the standard
library. When `input_model` is set, its JSON Schema is advertised to the model,
validated arguments are normalized before the handler runs, and invalid input
cannot invoke the handler. When `output_model` is set, the tool returns a
validated model instance and rejects invalid handler results.

```python
from maple import (
    AutonomousConfig,
    Tool,
    parse_structured_output,
    parse_typed_output,
)
from pydantic import BaseModel

report_schema = {
    "type": "object",
    "required": ["answer"],
    "properties": {"answer": {"type": "string", "minLength": 1}},
    "additionalProperties": False,
}

tool = Tool(
    name="report",
    description="Produce a report",
    parameters={"type": "object", "required": ["topic"]},
    handler=produce_report,
    result_schema=report_schema,
    input_guardrails=[lambda args: len(args["topic"]) <= 200],
)

config = AutonomousConfig(
    llm=llm_config,
    response_schema=report_schema,
    output_guardrails=[lambda value: value["answer"] != ""],
)
parsed = parse_structured_output('{"answer":"ready"}', report_schema)

class LookupArgs(BaseModel):
    topic: str

class LookupResult(BaseModel):
    answer: str

typed_tool = Tool(
    name="typed_lookup",
    description="Look up a topic",
    parameters={"type": "object"},
    handler=produce_typed_report,
    input_model=LookupArgs,
    output_model=LookupResult,
)
typed = parse_typed_output('{"answer":"ready"}', LookupResult)
```

### Bounded agent handoffs

`create_handoff_tool` exposes one specialist agent as a normal MAPLE `Tool`.
The model submits only a bounded `task` string; the result contains the target
agent ID, goal ID, status, and result. Handoffs require approval by default
because the target may call its own tools or create external side effects. An
explicit `allowed_context_keys` allowlist can permit bounded JSON context for a
target that declares `pursue_goal_with_context(task, context)`:

```python
from maple import create_handoff_tool

handoff = create_handoff_tool(
    specialist,
    allowed_context_keys=["project", "constraints"],
)
caller.register_tool(handoff)

result = handoff.execute(
    task="Summarize the release risks",
    context={"project": "MAPLE", "constraints": {"max_words": 200}},
)

# Async callers use the target's declared async handoff contract when present.
async def run_async():
    return await handoff.execute_async(
        task="Summarize the release risks",
        context={"project": "MAPLE", "constraints": {"max_words": 200}},
    )
```

The task is limited to 8,192 characters and rejects extra arguments. Context is
copied and bounded before filtering; an unknown key returns
`HANDOFF_CONTEXT_KEY_DENIED`, and a non-empty context sent to a legacy target
returns `HANDOFF_CONTEXT_UNSUPPORTED`. A target failure returns
`HANDOFF_TARGET_FAILED`, a raised exception returns `HANDOFF_TARGET_ERROR`, and
an invalid target result returns `HANDOFF_TARGET_INVALID`; raw target error
payloads are not forwarded. Set `requires_approval=False` only for a trusted
host-controlled handoff. The target's initial context message is part of a
durable local run checkpoint. `Tool.execute_async` awaits an async-capable
target and otherwise runs the synchronous compatibility path in an executor;
the async agent loop preserves the same approval boundary. Durable handoff
identity and ownership transfer can be enabled with `HandoffStore`; records
contain only bounded IDs, state, timestamps, and SHA-256 task/context digests.
`FileHandoffStore` uses atomic JSON replacement and the existing per-record
fencing lease. The record is accepted before target execution and finalized by
the target owner after execution:

```python
from maple import FileHandoffStore, create_handoff_tool

handoff = create_handoff_tool(
    specialist,
    handoff_store=FileHandoffStore(".maple-handoffs"),
    source_agent_id="orchestrator",
)
result = handoff.execute(task="Summarize the release risks")
# A successful result includes a bounded handoff_id.
```

`InMemoryHandoffStore` is available for local tests. Store failures fail closed
and finalization failures do not claim success. The store is an identity/state
journal, not a remote queue, scheduler, notification service, or exactly-once
side-effect mechanism; remote routing/authentication, hard target cancellation,
and distributed delivery remain separate capabilities.

### Per-goal token accounting and budgets

`Goal.token_usage` aggregates provider-reported prompt, completion, and total
tokens for the ReAct goal. Set `AutonomousConfig.max_total_tokens` to enforce
an opt-in hard budget in both `pursue_goal` and `pursue_goal_async`:

```python
config = AutonomousConfig(
    llm=llm_config,
    max_total_tokens=12_000,
)
goal_result = agent.pursue_goal("Complete the bounded task")
if goal_result.is_ok():
    goal = goal_result.unwrap()
    print(goal.token_usage.total_tokens)
```

When a budget is configured, every reasoning and reflection response must
include valid provider usage data. Missing or malformed usage fails closed with
`TOKEN_USAGE_UNAVAILABLE` or `TOKEN_USAGE_INVALID`; exceeding the budget
returns `TOKEN_BUDGET_EXCEEDED` before the response's tools execute. With the
default `None`, existing provider behavior is unchanged. Standalone
`decompose_goal` calls are outside this per-goal ReAct budget.

### Bounded multi-agent orchestration

`AgentOrchestrator` fans out independent supervised workers and consensus
members with a bounded in-process concurrency limit. Results are joined in
assignment order even when agents finish out of order. The asynchronous methods
prefer native `pursue_goal_async` implementations and use an executor for
sync-only agents:

```python
from maple import AgentOrchestrator, CancellationToken, TeamMember

orchestrator = AgentOrchestrator(max_parallel_agents=4)
token = CancellationToken()
team_id = orchestrator.form_team(
    "research",
    [
        TeamMember(agent=supervisor, role="supervisor"),
        TeamMember(agent=researcher_a, role="worker"),
        TeamMember(agent=researcher_b, role="worker"),
    ],
).unwrap()

result = await orchestrator.execute_supervised_async(
    team_id,
    "Compare sources",
    cancellation=token,
    timeout_seconds=30,
)
```

The limit is validated from 1 through 64. A member exception becomes an
`AGENT_EXECUTION_ERROR` entry for that member while sibling work continues.
`timeout_seconds` is one total budget covering decomposition, fan-out, and
collection; expiry returns `ORCHESTRATION_TIMEOUT`. A canceled request returns
`ORCHESTRATION_CANCELLED` after native async child tasks are canceled and
drained. Sync-only agents use an executor fallback and cannot be forcibly
stopped by Python, so their handlers must remain cooperative. This is bounded
local concurrency, not a distributed scheduler or untrusted execution sandbox.

### Bounded structured-output repair

Structured output remains fail-fast by default. Set
`AutonomousConfig.max_output_retries` from 1 through 3 to let the model correct
an invalid typed/schema response or output-guardrail rejection:

```python
config = AutonomousConfig(
    llm=llm_config,
    output_model=LookupResult,
    max_output_retries=1,
    max_total_tokens=12_000,
)
```

Each correction is a normal ReAct model response: it appears in
`goal.reasoning_trace`, consumes a reasoning step and provider tokens, and can
hit `max_total_tokens`. Exhaustion returns the original structured error. The
retry request includes only a controlled error type, not validation payloads.

### Bounded model/provider retry

Model retries are disabled by default. To retry transient provider failures in
both `pursue_goal` and `pursue_goal_async`, pass a `ModelRetryPolicy`:

```python
from maple import AutonomousConfig, ModelRetryPolicy

config = AutonomousConfig(
    llm=llm_config,
    model_retry_policy=ModelRetryPolicy(
        max_retries=2,
        base_delay_seconds=0.25,
        max_delay_seconds=2.0,
    ),
)
```

`max_retries` is capped at three and delays at 60 seconds. The default
retryable types are `LLM_RATE_LIMITED`, `LLM_TIMEOUT`, and
`LLM_TRANSIENT_ERROR`; hosts may provide a bounded tuple of exact uppercase
error types. Unknown, authentication, validation, and provider-installation
errors remain terminal. A retry is attempted before the current step can
execute tools, so no tool handler is replayed by this policy. A successful
response is accounted once.

When an `EventStream` is attached, each scheduled retry emits a bounded
`model.retry_scheduled` event containing `step`, `retry_count`, `max_retries`,
`delay_seconds`, and `error_type`, plus the normal `agent_id`/`run_id`
metadata. It never contains prompts, model output, credentials, or raw SDK
objects. OpenAI-compatible and Anthropic adapters classify common rate-limit,
timeout, and 5xx/connection failures; unknown exception types retain the
operation's existing terminal error type. This is a local request retry
boundary, not a durable distributed scheduler, hosted rate-limit service, or
exactly-once tool execution guarantee.

## Retrieval and Source References (preview)

The retrieval contract keeps document identity, source citations, chunk offsets,
metadata, and ranked hits together. `TextChunker` enforces document/chunk
bounds, while `InMemoryLexicalRetriever` and `InMemoryVectorRetriever` provide
dependency-free reference backends for local development and tests.

```python
from maple import (
    Document,
    InMemoryLexicalRetriever,
    SourceRef,
)

retriever = InMemoryLexicalRetriever()
retriever.add_document(
    Document(
        document_id="guide-1",
        text="MAPLE uses resource-aware agent orchestration.",
        source=SourceRef(uri="https://example.invalid/guide", title="Guide"),
    )
)
hits = retriever.search("resource-aware orchestration", top_k=3)
if hits.is_ok():
    for hit in hits.unwrap():
        print(hit.score, hit.chunk.source.uri, hit.chunk.text)
```

The reference backend is intentionally local; it is not a hosted vector
database or embedding service. A vector index accepts one finite, bounded
embedding per generated chunk and uses cosine similarity with deterministic
tie-breaking:

```python
from maple import Document, InMemoryVectorRetriever, SourceRef

vector_retriever = InMemoryVectorRetriever()
vector_retriever.add_document(
    Document(
        document_id="guide-1",
        text="MAPLE uses resource-aware agent orchestration.",
        source=SourceRef(uri="https://example.invalid/guide"),
    ),
    [(0.8, 0.2, 0.1)],  # supplied by the host's pinned embedding pipeline
)
hits = vector_retriever.search((0.7, 0.3, 0.1), top_k=3)
```

MAPLE does not select or call an embedding model. Empty/malformed/oversized
inputs fail with structured `Result` errors, and every hit carries a source
reference for citation.

## Event Streaming and Redaction (preview)

`EventStream` provides an in-process observability contract for workflow, model,
and tool lifecycle events. It assigns monotonic sequence numbers, retains a
bounded ring, supports snapshots/waiters and synchronous subscribers, and
redacts credential-like keys before retention or delivery. A host-owned
`EventExporter` may receive each already-redacted event; exporter exceptions
are isolated from the run. Payload shape,
string, item, depth, and byte limits fail closed with structured errors. The
autonomous agent can publish a shared sync/async run lifecycle through
`set_event_stream()`.

```python
from maple import EventStream

events = EventStream(max_events=1_000, max_payload_bytes=64_000)
events.publish(
    "tool.completed",
    {"tool": "search", "api_key": "never-retained"},
    run_id="run-1",
)
for event in events.snapshot().unwrap():
    print(event.sequence, event.event_type, event.payload)
```

An exporter is intentionally synchronous and local; hosts that need queues,
durability, retries, or remote telemetry must own that boundary:

```python
from maple import EventExporter, EventStream

class JsonExporter:
    def export(self, event):
        print(event.as_dict())

events = EventStream(exporter=JsonExporter())
```

For incremental consumers, persist an `EventCursor` and use bounded reads. A
cursor older than the retained ring fails with `EVENT_CURSOR_EXPIRED` rather
than silently skipping events:

```python
from maple import EventCursor, EventStream

events = EventStream(max_events=100)
cursor = EventCursor()
batch = events.read(cursor, limit=25).unwrap()
cursor = batch.next_cursor
saved_cursor = cursor.to_dict()
restored = EventCursor.from_dict(saved_cursor).unwrap()
next_batch = events.read(restored, limit=25)
```

`EventStream.wait_for(..., cancellation=token)` accepts MAPLE's cooperative
`CancellationToken` contract and returns `EVENT_CANCELLED` when signalled. This
is a local event contract, not a durable broker, remote transport, or hosted
telemetry service. Provider-native `LLMChunk` streams can expose a bounded
final `TokenUsage` trailer and request correlation ID when the provider emits
them; OpenAI-compatible providers opt into the usage request with
`LLMConfig.extra["include_stream_usage"] = True`. Subscribers and exporters are
synchronous and
should hand off to a host-owned queue when callback work may block. The agent
lifecycle uses metadata-only events and usage trailers; set
`AutonomousConfig.stream_model_events=True` to aggregate provider chunks for a
ReAct step and emit one `model.chunk` event per bounded chunk before the final
`model.response`. Chunk events contain byte counts, tool-call presence,
finish/usage metadata, and safe provider request IDs; prompts, chunk content,
tool arguments, tool output, and final result data are not emitted. The
collector reconstructs text and JSON tool arguments into the normal
`LLMResponse` contract and fails closed on malformed or over-quota streams.
Bounded provider request IDs are copied into `model.response` events and
`DecisionTrace` records for local joins. `dropped_count` exposes bounded-ring
eviction, while cursor reads make that gap explicit.

`EventStream.metrics()` returns a thread-safe snapshot of retained events,
configured capacity, evictions, subscriber count, accepted publishes,
subscriber/exporter failures, and integer-millisecond publish latency totals,
maximum, average, p50, p95, and p99. `SpanRecorder.metrics()` returns span
capacity/eviction/open-span counts, sampled-out spans, completed spans,
terminal status counts, and the same integer latency views. Percentiles use a
bounded ring of at most 4,096 recent samples (also limited by the configured
event/span capacity); empty samples return zero. These are local snapshots;
they do not export or persist telemetry and do not represent a fleet-wide
distribution.

```python
from maple import AutonomousAgent, AutonomousConfig, Config, EventStream, LLMConfig

agent = AutonomousAgent(
    Config(agent_id="demo", broker_url="memory://demo"),
    AutonomousConfig(
        llm=LLMConfig(provider="openai", model="gpt-4o-mini"),
        stream_model_events=True,
    ),
)
agent.set_event_stream(EventStream())
```

For local trace correlation, attach a bounded `SpanRecorder`. It records one
`agent.model` span per ReAct model step and one `agent.tool` child span for
each normal tool execution. Model spans copy their `trace_id` and `span_id`
into model chunk/response events and `DecisionTrace` records. Tool spans use
the open model span as their parent and retain only bounded tool identity,
step, error status, and result length. Span attributes are redacted and
limited to flat JSON scalars; recording failures are observational and do not
change the run result.

```python
from maple import SpanRecorder

spans = SpanRecorder(max_spans=1_000, sample_rate=0.25)
agent.set_span_recorder(spans)
completed = agent.pursue_goal("Summarize this document.")
for span in spans.snapshot().unwrap():
    print(span.name, span.status, span.trace_id, span.span_id)
print(spans.metrics()["sampled_out_spans"])
```

Sampling uses a stable local hash bucket and returns a typed
`SPAN_SAMPLED_OUT` result for spans not retained; the agent treats that
observability result as non-fatal. This is an in-process inspection contract.
Percentile latency histograms, durable/remote exporters, approval-replay
correlation, and hosted trace search remain host-owned or deferred.

## Evaluation and Provider Capabilities (preview)

The evaluation harness runs local runners against versioned golden cases. A
case can assert exact output, a bounded JSON schema, and an ordered tool
trajectory. `fixture_version` defaults to 1 and is reported with each result;
trajectory expectations are bounded to 256 tool names. Failures are recorded
per case so one bad case does not abort the report; actual values are redacted
and size-bounded before they are returned.

```python
from maple import EvalCase, EvalObservation, EvaluationHarness

cases = [
    EvalCase(
        case_id="lookup",
        input={"query": "MAPLE"},
        output_schema={"type": "object", "required": ["answer"]},
        expected_tool_names=("search",),
    )
]
report = EvaluationHarness().run(
    cases,
    lambda value: EvalObservation(
        output={"answer": "ready"},
        tool_names=("search",),
    ),
)
```

An optional host-supplied judge can add a generation-quality check without
making MAPLE select a provider. The callback receives the case and a redacted,
bounded `EvalObservation`, and returns `EvalJudgeResult` directly or through
`Result`. Its score must be finite and between 0 and 1, and its explicit
`passed` decision participates as one additional report check.

```python
from maple import EvalJudgeResult

case = EvalCase(
    case_id="lookup-v2",
    input={"query": "MAPLE"},
    output_schema={"type": "object", "required": ["answer"]},
    expected_tool_names=("search",),
    fixture_version=2,
)
report = EvaluationHarness().run(
    [case],
    lambda value: EvalObservation(
        output={"answer": "ready"},
        tool_names=("search",),
    ),
    judge=lambda fixture, observation: EvalJudgeResult(
        score=0.9,
        passed=True,
        rationale="answer is relevant",
    ),
)
```

Judge errors, exceptions, malformed results, and invalid bounds fail the
individual case with typed errors. MAPLE does not invoke or retry a model
provider, calibrate scores, or claim semantic faithfulness; provider choice,
rubric, privacy, and repeatability remain host-owned.

Retrieval quality can be evaluated separately from answer generation with
bounded golden source URIs. `run_retrieval` accepts lexical
`RetrievalHit` or vector `VectorRetrievalHit` values, deduplicates source URIs,
and reports source-level precision, recall, and F1. It does not claim answer
faithfulness or entailment.

```python
from maple import EvaluationHarness, RetrievalEvalCase

case = RetrievalEvalCase(
    case_id="policy-lookup-v1",
    query="MAPLE resource messaging",
    expected_source_uris=("urn:docs:messaging",),
    min_precision=1.0,
    min_recall=1.0,
)
report = EvaluationHarness().run_retrieval(
    [case],
    lambda query: retriever.search(query).unwrap(),
)
```

Malformed hit sequences, runner errors, and exceptions are isolated as typed
per-case failures. Golden source sets are host-maintained; calibrated
generation evaluation and LLM-as-judge workflows remain separate contracts.

`run_groundedness` provides a deterministic lexical claim-support proxy over
bounded source URI/text pairs. It splits a generated answer into bounded
claims, removes a small fixed English stopword set, and marks a claim supported
when token overlap with one source reaches `min_claim_overlap`.

```python
from maple import (
    EvaluationHarness,
    GroundednessEvalCase,
    GroundednessObservation,
    GroundingSource,
)

case = GroundednessEvalCase(
    case_id="answer-grounding-v1",
    query="What does MAPLE provide?",
    sources=(
        GroundingSource(
            "urn:docs:maple",
            "MAPLE provides resource aware messaging for agents.",
        ),
    ),
    min_supported_ratio=1.0,
    min_claim_overlap=0.75,
)
report = EvaluationHarness().run_groundedness(
    [case],
    lambda query: GroundednessObservation(
        "MAPLE provides resource aware messaging for agents."
    ),
)
```

Runner failures, malformed observations, oversized values, and low support
ratios are returned as typed per-case failures. This metric is a reproducible
lexical proxy, not semantic entailment, factuality, citation faithfulness, or
an LLM-as-judge result; paraphrase, contradiction, and multilingual quality
need a separate calibrated evaluation contract.

Providers can declare compatibility requirements independently of provider
names. `ProviderRouter` orders matching descriptors by explicit priority and
tries configured providers in that order, returning a structured failure if no
compatible provider initializes.

```python
from maple import ProviderCapabilities, ProviderRequirements, ProviderRouter

router = ProviderRouter()
router.register(
    "local",
    LocalProvider,
    ProviderCapabilities(tools=True, structured_output=True),
    priority=10,
)
provider = router.create(
    {"local": local_config},
    ProviderRequirements(tools=True, structured_output=True),
)
```

## Interoperability and Doctor CLI (preview)

`InteropEnvelope` is a strict versioned JSON envelope for adapter round-trip
fixtures. It rejects unknown top-level fields, unsupported schema versions,
non-JSON values, and oversized payloads.

```python
from maple import InteropEnvelope, round_trip_json

envelope = InteropEnvelope(
    protocol="a2a",
    message_type="TASK",
    payload={"task": "research"},
)
round_tripped = round_trip_json(envelope)
```

For local release preflight, run `maple doctor --json`. It reports the runtime
surface checks without contacting providers or cloud services; it does not
replace the full test, lint, type, dependency-audit, and packaging gates.

## Workflow Runtime (preview)

The workflow runtime provides a dependency-free execution graph with
JSON-safe checkpoints. A node receives a `WorkflowContext` and returns a
mapping of state updates, `Result.ok(updates)`, or `Result.err(error)`. Raise
`WorkflowPause(payload)` when external input is required; resume the same run
with the checkpoint store that was used to start it.

```python
from maple import FileCheckpointStore, Workflow, WorkflowPause

store = FileCheckpointStore("./.maple-checkpoints")
workflow = Workflow("approval_flow", checkpoint_store=store)

workflow.add_node("prepare", lambda ctx: {"ready": True})

def approve(ctx):
    if ctx.resume_value is None:
        raise WorkflowPause({"question": "Approve this action?"})
    return {"approved": ctx.resume_value}

workflow.add_node("approve", approve)
workflow.add_node("finish", lambda ctx: {"done": True})
workflow.set_entry_point("prepare")
workflow.add_edge("prepare", "approve")
workflow.add_edge("approve", "finish")
workflow.add_edge("finish")

run = workflow.run({"request": "example"}, run_id="example-1")
if run.is_ok() and run.unwrap().status == "interrupted":
    run = workflow.resume("example-1", resume_value=True)
```

Independent branches can run concurrently and join at a durable checkpoint.
Branch outputs must use distinct state keys; the declaration order controls the
deterministic merge and checkpoint history. The branch limit defaults to eight
and can be set with `max_parallel_branches` up to 64.

```python
workflow = Workflow("research", max_parallel_branches=2)
workflow.add_node("start", lambda ctx: {"query": "MAPLE"})
workflow.add_node("web", lambda ctx: {"web_result": "..."})
workflow.add_node("docs", lambda ctx: {"docs_result": "..."})
workflow.add_node("join", lambda ctx: {"ready": True})
workflow.set_entry_point("start")
workflow.add_fan_out("start", ("web", "docs"), "join")
workflow.add_edge("join")
```

### Bounded workflow retry

Pass `RetryPolicy` values through `retry_policies=` or register one with
`set_retry_policy(node_name, policy)`. `max_retries` is the number of retries
after the initial attempt and is capped at eight; delays use capped exponential
backoff with a maximum of 60 seconds. The current `retry_count` is available in
`WorkflowContext`, and retry counts plus scheduled retry timestamps are persisted
in `WorkflowCheckpoint` so `recover()` can continue the same bounded policy after
a process restart. The same policy applies to ordinary nodes and named fan-out
branches; branch attempts are retried in bounded waves and successful branches
are not re-executed within the current process.

```python
from maple import RetryPolicy, Workflow

workflow = Workflow(
    "resilient_flow",
    retry_policies={
        "fetch": RetryPolicy(
            max_retries=2,
            base_delay_seconds=0.25,
            max_delay_seconds=2.0,
        )
    },
)
workflow.add_node("fetch", lambda ctx: {"retry": ctx.retry_count})
```

When a node or branch fails, MAPLE persists `NODE_RETRY_SCHEDULED` before
retrying. When the policy is exhausted, the run fails with
`NODE_RETRY_EXHAUSTED` and retains the retry count. Branch checkpoints expose
`branch_retry_counts` and `branch_retry_after`; `WorkflowRun` exposes the same
diagnostic fields. External side effects still require idempotent handlers.

Checkpoint data accepts JSON-compatible values only, is size-bounded, and is
restored as data rather than executable objects. The current file store is
atomic and thread-safe within one process. Fan-out uses bounded trusted
in-process threads; it is not a hard sandbox, and a pause before the group
checkpoint may repeat branch side effects when resumed. Per-branch retry state is
durable in the configured checkpoint store, but the local runtime does not claim
distributed scheduling or exactly-once effects. The history decorator below
provides bounded current-process inspection, while the optional execution journal
provides a separate crash-window recovery surface.

Wrap any checkpoint store with `HistoryCheckpointStore` to retain bounded
immutable snapshots for current-process inspection:

```python
from maple import HistoryCheckpointStore, InMemoryCheckpointStore

history_store = HistoryCheckpointStore(
    InMemoryCheckpointStore(), max_history=100
)
workflow = Workflow("inspectable", checkpoint_store=history_store)
# ... define and run the workflow ...
snapshots = history_store.history(run_id, limit=20)
```

History is ordered by checkpoint version and returns JSON-safe copies. It is an
inspection surface, not executable replay: node handlers are never re-run, and
the history decorator does not claim cross-process or restart persistence.

### Bounded workflow execution journal

Pass an `InMemoryExecutionJournal` or `FileExecutionJournal` to `Workflow` to
record normalized node outputs before their checkpoint commit. If a host keeps
a `running` checkpoint after a crash or checkpoint-store failure, call
`workflow.recover(run_id)`; the journal can reuse the recorded output and avoid
re-running that handler. `WorkflowContext.execution_key` exposes the stable
`run_id:step_count:node_name` key for logging or idempotency coordination.

```python
from maple import FileCheckpointStore, FileExecutionJournal, Workflow

checkpoint_store = FileCheckpointStore("./.maple-checkpoints")
execution_journal = FileExecutionJournal("./.maple-replay")
workflow = Workflow(
    "recoverable_flow",
    checkpoint_store=checkpoint_store,
    execution_journal=execution_journal,
)
# ... define the workflow and run it ...
recovered = workflow.recover("run-1")
```

Journal records and inputs are JSON-safe, hashed, atomically persisted, and
bounded by record and run quotas. The journal closes the normalized-output
crash window only when its record was saved before the crash; it does not claim
exactly-once execution or make arbitrary external side effects safe. Handlers
that call external systems still need idempotency keys or transactional
coordination. Use `execution_journal.clear(run_id)` after retention is no
longer required.

### Durable tool approvals

Approval-required autonomous tools can use a local durable approval store when
the host cannot provide a synchronous callback. The agent creates a bounded
pending request and never invokes the handler until the host records a decision
and consumes the approval.

```python
import json

from maple import FileApprovalStore

store = FileApprovalStore("./.maple-approvals")
agent.set_approval_store(store)

goal = agent.pursue_goal("perform the approval-gated action")
pending = goal.unwrap().reasoning_trace[-1].tool_results[-1]
approval_id = json.loads(pending.content)["details"]["approval_id"]
decision = agent.decide_approval(
    approval_id,
    approved=True,
    edited_arguments={"key": "status", "value": "corrected"},
)
if decision.is_ok():
    result = agent.execute_approved_tool(approval_id)
```

`decide_approval` is a pending-to-approved/denied compare-and-set operation;
an approved decision may include a bounded JSON `edited_arguments` replacement.
`None` keeps the original model arguments, while `{}` intentionally supplies an
empty object. Invalid edits or edits attached to a denial return
`APPROVAL_DECISION_INVALID` without changing the pending record.
`execute_approved_tool` claims the request before executing it and a second
attempt in the same process returns `APPROVAL_CONSUMED`. File persistence is
atomic and thread-safe within one process, and `FileApprovalStore` acquires a
per-record `FileLeaseManager` fencing lease by default under
`<directory>/.maple-leases`. Pass `lease_manager=` to provide a caller-owned
manager or `lease_ttl_seconds=` to change the bounded 30-second default.
Failed acquisition returns `APPROVAL_LEASE_ERROR` without mutation; failed
release returns `APPROVAL_LEASE_RELEASE_ERROR` and means the mutation may
already be committed, so inspect the record before retrying. Approval arguments
may contain application-sensitive data and
should be protected with host filesystem access controls. The store does not
persist the full ReAct conversation, does not implement arbitrary
request/response HITL forms, and failed tool execution requires a new approval
request.

### Durable human input

Durable ReAct runs can expose the built-in `request_human_input` tool to ask
the host a bounded question or form. The request is persisted with its prompt
and JSON-Schema response contract; the agent pauses before any later tool
calls.

```python
import json

from maple import FileAgentRunStore, FileHumanInputStore

run_store = FileAgentRunStore("./.maple-runs")
input_store = FileHumanInputStore("./.maple-input")
agent.set_run_store(run_store)
agent.set_human_input_store(input_store)

goal = agent.pursue_goal("Deploy after human confirmation", run_id="deploy-1")
interaction_id = goal.unwrap().result["details"]["interaction_id"]
request = input_store.get(interaction_id).unwrap()
assert request is not None

agent.respond_human_input(interaction_id, {"confirmed": True})
resumed = agent.resume_run("deploy-1")
```

`respond_human_input` validates the response against the request's bounded
schema and leaves a pending request unchanged on failure. Use
`reject_human_input(interaction_id, reason)` to resume with a typed
`HUMAN_INPUT_REJECTED` tool error. Requests default to one round; pass
`max_rounds` to the built-in tool, then call
`continue_human_input(interaction_id, prompt, input_schema)` after a decided
round to reopen the same interaction with bounded persisted history. Continue
before resuming a durable run when the checkpoint should wait for the next
round. A round's consumed decision is retained for crash recovery, and a
response after the configured round limit returns `HUMAN_INPUT_ROUND_LIMIT`.
The built-in tool requires a durable `run_id`; it does
not collect input in a non-durable run. `FileHumanInputStore` acquires a
per-record `FileLeaseManager` fencing lease by default under
`<directory>/.maple-leases`; `lease_manager=` and `lease_ttl_seconds=` are
available for caller-owned coordination. Acquisition failure returns
`HUMAN_INPUT_LEASE_ERROR` without mutation; release failure returns
`HUMAN_INPUT_LEASE_RELEASE_ERROR` and requires record inspection before retry.
Pass `notifier=` to either human-input store for bounded `created`,
`responded`, and `rejected` lifecycle callbacks. Notifications contain request
metadata and optional `actor_id`, but never the submitted response payload;
notification failure returns `HUMAN_INPUT_NOTIFICATION_ERROR` after persistence,
so inspect the authoritative record before retrying. Pass `authorizer=` to
either store to require an `actor_id` on `respond` and `reject`; the callback
runs inside the record lease and missing, denied, exceptional, or malformed
authorization returns a typed fail-closed error. `AutonomousAgent` forwards
`actor_id=` through `respond_human_input` and `reject_human_input`. These are
local caller-owned hooks, not credential verification or a remote transport;
remote authentication and transport remain follow-on responsibilities.

### Bounded conversation sessions

`SessionMessage` and `SessionSnapshot` provide a JSON-safe turn-history
boundary. `InMemorySessionStore` is useful for tests and short-lived hosts;
`FileSessionStore` uses atomic JSON replacement for local process-restart
recovery.

```python
from maple import FileSessionStore, SessionMessage

store = FileSessionStore("./.maple-sessions", max_messages=100)
created = store.create("chat-1", metadata={"tenant": "demo"})
stored = store.append(
    "chat-1",
    SessionMessage(role="user", content="Summarize this document."),
    expected_version=created.unwrap().version,
)
snapshot = stored.unwrap()
```

Session IDs, roles, metadata, message count, message bytes, and serialized
session bytes are bounded before mutation. Appends and clears accept an
optional expected version and return `SESSION_CONFLICT` on a stale version.
Returned snapshots are fresh JSON-safe copies. File persistence is
thread-safe within one process; encryption, cross-process leases, and
summarization remain separate host/runtime decisions.

`AutonomousAgent` can bind these sessions explicitly for multi-turn context:

```python
from maple import InMemorySessionStore

agent.set_session_store(InMemorySessionStore())
goal = agent.pursue_goal("Summarize this document.", session_id="chat-1")
```

The current user turn is appended with an optimistic version check before the
LLM runs. Only stored `user` and `assistant` messages are replayed; stored
`system` and `tool` messages remain data and are not promoted into the prompt.
The same contract is available through `pursue_goal_async`. If execution
finishes but the assistant result cannot be persisted, the returned `Goal`
remains available and exposes the typed failure in `goal.session_error`.
Without `session_id`, existing agent behavior is unchanged. Full ReAct trace
replay, tool-result replay, compaction, authentication, and cross-process
turn leases remain separate capabilities.

### Durable agent runs (preview)

Attach an `InMemoryAgentRunStore` or `FileAgentRunStore` to persist a bounded
JSON-safe ReAct message cursor. Supplying `run_id` makes a new goal resumable;
`resume_run()` loads the latest checkpoint and continues from the next model
step. The store uses compare-and-set versions and atomic file replacement, is
thread-safe within one process, and does not serialize Python objects. A
`FileAgentRunStore` acquires a per-run `FileLeaseManager` fencing lease by
default under `<directory>/.maple-leases`; pass `lease_manager=` for
caller-owned coordination or `lease_ttl_seconds=` to override the bounded
30-second default. Failed acquisition returns `RUN_CHECKPOINT_LEASE_ERROR`
without reading or mutating the checkpoint; failed release returns
`RUN_CHECKPOINT_LEASE_RELEASE_ERROR` and means a save may already be durable,
so inspect the checkpoint before retrying.

```python
from maple import FileAgentRunStore

agent.set_run_store(FileAgentRunStore("./.maple-runs"))
started = agent.pursue_goal("Review this request", run_id="review-1")

# A new agent instance configured with the same store can recover the run.
recovered = restarted_agent.resume_run("review-1")
```

The async entry point uses the same checkpoint contract and keeps file-backed
store I/O off the event loop:

```python
started = await agent.pursue_goal_async("Review this request", run_id="review-2")
recovered = await restarted_agent.resume_run_async("review-2")
```

When a tool requires durable approval, the run returns a `Goal` with
`status == "paused"` and an `AGENT_RUN_PAUSED` result containing the bounded
`run_id` and `approval_id`. After `decide_approval`, `resume_run()` replaces
the pending tool placeholder with the approved or denied result before asking
the model for another step. A pending run without a decision returns
`RUN_WAITING_APPROVAL`. Completed tool calls are represented in the checkpoint
before the next model call, but external side effects remain at-least-once and
must be made idempotent by the handler when required.

Both sync and async run paths checkpoint the initial message cursor and each
completed ReAct step. When durable persistence is enabled, async tool calls in
one model step are executed in order so an approval pause happens before later
tool side effects. The local store fences one run cursor at a time across local
processes; it is not a distributed identity or side-effect service. External
effects remain at-least-once and handler idempotency remains the host's
responsibility. Full trace replay, durable
streaming cursors, arbitrary request/response HITL, and sandboxing are separate
capabilities.

### Loopback workflow run server

`WorkflowRegistry` and `RunServer` expose configured workflows to local tools
without adding an HTTP framework. Register workflows before starting the
server; the server binds to `127.0.0.1` by default and owns a daemon request
thread that `close()` shuts down.

```python
from maple import RunServer, WorkflowRegistry

registry = WorkflowRegistry()
registry.register(workflow)

with RunServer(registry) as server:
    print(server.url)
    # POST /v1/workflows/<workflow>/runs
    # POST /v1/workflows/<workflow>/runs/<run_id>/resume
    # GET  /v1/workflows/<workflow>/runs/<run_id>
```

`GET /healthz` returns `{"status": "ok", "service":
"maple-run-server"}`. Run creation returns `201` and resume/inspection return
`200`; errors use `{"error": {"errorType": ..., "message": ...}}` with
`400`, `404`, `409`, `413`, or `500` status codes. Run bodies require
`application/json`; request and response bytes are bounded, and workflow
state/resume values still pass through the workflow JSON boundary. This is a
local host surface, not an authenticated or TLS-enabled remote service: no
non-loopback host, arbitrary workflow registration, streaming transport,
multi-tenant authorization, or hard sandbox is claimed.

## Usage Example

```python
from maple import Agent, Message, Priority, Config, SecurityConfig, Result

# Configure agent
config = Config(
    agent_id="my_agent",
    broker_url="memory://local",
    security=SecurityConfig(
        auth_type="token",
        credentials="my_token",
        require_links=True
    )
)

# Create and start agent
agent = Agent(config)
agent.start()

# Register handler
@agent.handler("TASK")
def handle_task(message):
    data = message.payload.get("data")
    return Message(
        message_type="TASK_RESULT",
        receiver=message.sender,
        payload={"result": f"processed {data}"}
    )

# Send a message
result = agent.send(Message(
    message_type="TASK",
    receiver="other_agent",
    priority=Priority.HIGH,
    payload={"data": "input"}
))

if result.is_ok():
    print(f"Sent: {result.unwrap()}")
else:
    print(f"Error: {result.unwrap_err()}")

# Establish secure link
link_result = agent.establish_link("other_agent", lifetime_seconds=3600)
if link_result.is_ok():
    link_id = link_result.unwrap()
    secure_msg = Message(
        message_type="SECURE_TASK",
        receiver="other_agent",
        payload={"sensitive": "data"}
    ).with_link(link_id)
    agent.send_with_link(secure_msg, "other_agent")

agent.stop()
```

---

**Creator: Mahesh Vaijainthymala Krishnamoorthy (Mahesh Vaikri)**

```text
Copyright (C) 2025 Mahesh Vaijainthymala Krishnamoorthy (Mahesh Vaikri)
Licensed under the GNU Affero General Public License v3.0 (AGPL-3.0)
See LICENSE for details.
```
