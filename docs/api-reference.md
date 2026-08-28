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

## Task Management (preview)

`TaskQueue` is the local priority-aware task admission and assignment surface.
Its constructor accepts an integer capacity from `1` through `100,000`. The
capacity is global across `CRITICAL`, `HIGH`, `NORMAL`, `LOW`, and
`BACKGROUND`; it is not multiplied by the number of priority queues.

```python
from maple.task_management.task_queue import TaskPriority, TaskQueue

queue = TaskQueue(max_queue_size=2)
first = queue.submit_task("research", {"query": "MAPLE"}, TaskPriority.HIGH)
second = queue.submit_task("summarize", {"text": "..."})
overflow = queue.submit_task("extra", {})

assert first.is_ok() and second.is_ok()
assert overflow.is_err()  # Queue is full

queue.start()
try:
    assigned = queue.get_next_task(timeout_seconds=0.1)
finally:
    queue.stop()
```

The public queue methods use one lock for admission, assignment, status, and
requeue state. A cancelled or completed task whose physical priority-queue
tuple has not yet been removed is treated as stale and never assigned. A
requeue rejected by the global capacity check leaves the failed task's status,
retry count, and error unchanged. This is an in-process queue contract; it
does not provide durable queue storage, distributed worker ownership, hosted
scheduling, force cancellation, or exactly-once external effects.

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
```

### Guardrail lifecycle events

`run_guardrails(...)` can receive an optional `GuardrailObserver`. The observer
gets immutable `GuardrailEvent` records for each ordered transition:
`started`, `passed`, `rejected`, or `failed`. Events contain only the stage,
guardrail index, status, and optional bounded trace/span IDs; guarded values and
raw callback errors are never copied. Observer exceptions are ignored so
observability cannot weaken fail-closed enforcement.

```python
from maple import GuardrailEvent, run_guardrails

events: list[GuardrailEvent] = []
decision = run_guardrails(
    {"answer": "ready"},
    [lambda value: True],
    stage="agent:output",
    observer=events.append,
    trace_id="run-123",
    span_id="span-456",
)
assert decision.is_ok()
assert [event.status for event in events] == ["started", "passed"]
```

When an `AutonomousAgent` has an `EventStream`, its input/output guardrails
publish the same metadata as `guardrail.started`, `guardrail.passed`,
`guardrail.rejected`, and `guardrail.failed`, linked to the local run and
active model span where available. Publication remains best-effort under the
bounded event-stream contract.

```python
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

### Manager-style agent-as-tool delegation

`create_agent_tool` exposes a specialist as a normal `Tool` while the calling
agent keeps orchestration ownership. It does not create a `HandoffRecord` or
transfer ownership. Approval is required by default because the nested agent
may use tools of its own:

```python
from maple import create_agent_tool

specialist_tool = create_agent_tool(
    specialist,
    allowed_context_keys=["project", "constraints"],
)
manager.register_tool(specialist_tool)

result = specialist_tool.execute(
    task="Summarize the release risks",
    context={"project": "MAPLE", "constraints": {"max_words": 200}},
)
assert result.is_ok()
assert result.unwrap()["status"] == "completed"
```

The bounded result contains only `agent_id`, `goal_id`, `status`, and `result`;
child prompts, traces, provider objects, and raw child errors are not forwarded.
Context is copied before filtering. A key outside `allowed_context_keys` returns
`AGENT_TOOL_CONTEXT_KEY_DENIED`, and non-empty context sent to a target without
`pursue_goal_with_context(...)` returns `AGENT_TOOL_CONTEXT_UNSUPPORTED`.
Target failures, raised exceptions, and malformed goals return typed
`AGENT_TOOL_TARGET_FAILED`, `AGENT_TOOL_TARGET_ERROR`, or
`AGENT_TOOL_TARGET_INVALID` errors without the child payload. When the target
declares `pursue_goal_async(...)`, `await specialist_tool.execute_async(...)`
uses that contract; otherwise the normal synchronous compatibility path runs in
the tool executor. Remote routing, durable child-run replay, automatic retries,
and exactly-once effects remain outside this local contract.

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
reference for citation. A host can add a provider-neutral reranking step to
either lexical or vector hits. The callback receives the query and bounded
`DocumentChunk`, and returns one finite score; MAPLE retains the original
retrieval score and uses deterministic chunk-ID tie-breaking:

```python
from maple import Document, InMemoryLexicalRetriever, SourceRef, rerank_hits
from maple.core.result import Result

retriever = InMemoryLexicalRetriever()
retriever.add_document(
    Document(
        document_id="guide-1",
        text="MAPLE uses resource-aware agent orchestration.",
        source=SourceRef(uri="https://example.invalid/guide"),
    )
)
candidates = retriever.search("agent orchestration", top_k=5)


class HostReranker:
    def score(self, query, chunk):
        return Result.ok(1.0 if "resource" in chunk.text else 0.5)


if candidates.is_ok():
    reranked = rerank_hits(query="agent orchestration", candidates=candidates.unwrap(), reranker=HostReranker())
```

The reranker is host-owned: it adds no provider dependency, makes no network
call, and does not claim that its score measures semantic faithfulness. The
default candidate bound is `100`; callback errors, invalid candidate values,
and non-finite scores fail closed with typed errors.

Hosts can load documents from a file, API, or managed store through the
provider-neutral connector seam. A connector returns bounded cursor pages, and
`ingest_documents(...)` sends each validated page to an explicit sink:

```python
from maple import (
    Document,
    DocumentBatch,
    FileDocumentCursorCheckpointStore,
    InMemoryDocumentConnectorRateLimiter,
    InMemoryLexicalRetriever,
    SourceRef,
    ingest_documents,
)
from maple.core.result import Result

source = SourceRef(uri="memory://connector")
document_a = Document("doc-a", "first connector document", source)
document_b = Document("doc-b", "second connector document", source)


class Connector:
    def fetch(self, cursor, *, limit):
        if cursor is None:
            return Result.ok(DocumentBatch((document_a,), "page-2"))
        return Result.ok(DocumentBatch((document_b,), None))


sink = InMemoryLexicalRetriever()
checkpoint_store = FileDocumentCursorCheckpointStore("./maple-checkpoints")
rate_limiter = InMemoryDocumentConnectorRateLimiter(
    max_calls=10,
    window_seconds=60.0,
)
report = ingest_documents(
    Connector(),
    sink,
    batch_size=50,
    max_documents=500,
    checkpoint_store=checkpoint_store,
    rate_limiter=rate_limiter,
)
if report.is_ok():
    print(report.unwrap().to_dict())
```

Connector pages are capped at `100` documents, one call is capped at `10,000`
documents and `100` batches, and repeated IDs or stalled cursors fail closed.
`InMemoryDocumentCursorCheckpointStore` and
`FileDocumentCursorCheckpointStore` provide optional bounded restart state;
file writes are atomic and revision-fenced, and `clear()` resets the cursor
while retaining the fencing revision. A checkpoint advances only after the
page's sink writes succeed, so restart behavior is explicitly at-least-once
at the connector-to-sink boundary. The helper performs no network calls,
retries, transactions, rollback, or managed-store selection; without a
checkpoint store, the host can resume using the reported cursor.
`InMemoryDocumentConnectorRateLimiter` optionally admits a bounded number of
fetches in a trailing time window and returns a typed rate-limit error when
the budget is exhausted. It never sleeps or retries; hosts own backoff and
remote/provider-specific limits. Custom `DocumentConnectorRateLimiter`
implementations must return `Result.ok(None)` to admit a fetch.

## Event Streaming and Redaction (preview)

`EventStream` provides an in-process observability contract for workflow, model,
and tool lifecycle events. It assigns monotonic sequence numbers, retains a
bounded ring, supports snapshots/waiters and synchronous subscribers, and
redacts credential-like keys before retention or delivery. A host-owned
`EventExporter` may receive each already-redacted event; the optional
`HttpEventExporter` provides bounded best-effort HTTP delivery and exporter exceptions
are isolated from the run. `EventForwarder` and `HttpEventBatchSender` provide
an explicit, bounded remote aggregation pump with a host-owned cursor.
`EventForwarderScheduler` adds an opt-in local polling worker with one active
tick, a finite interval, a bounded batch budget, cooperative shutdown, and
local integer metrics. Payload shape,
string, item, depth, and byte limits fail closed with structured errors. The
autonomous agent can publish a shared sync/async run lifecycle through
`set_event_stream()`.

For local process-restart replay, attach a `FileEventJournal` with the same
`max_events` as the stream. It stores a versioned bounded JSON event window by
atomic replacement and fences each load/append with a host-local lease. The
stream re-applies redaction when hydrating the window and resumes its sequence
after the persisted tail. Malformed, oversized, or non-monotonic journal state
fails closed during stream construction; an append failure prevents retention,
subscriber callbacks, and exporter delivery for that event. `FileEventCursorStore`
adds atomic, fenced persistence for an `EventForwarder` consumer position.

```python
from maple import EventStream, FileEventJournal

journal = FileEventJournal(".maple-events", max_events=100)
events = EventStream(max_events=100, journal=journal)
events.publish("tool.completed", {"status": "ok"})

# A new EventStream with the same journal rehydrates the retained window.
restarted = EventStream(
    max_events=100,
    journal=FileEventJournal(".maple-events", max_events=100),
)
```

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

`HttpEventExporter` is synchronous and performs one POST per event. It requires
a finite timeout, bounds event/response bytes, sends optional bearer auth only
in a header, requires HTTPS for non-loopback endpoints, and performs no retry
or persistence. `HttpEventBatchSender` performs one bounded POST to an existing
batch endpoint and parses a complete indexed acknowledgement. Use a host-owned
queue or an explicit `EventForwarder` when the collector may block:

```python
from maple import EventExporter, EventStream

class JsonExporter:
    def export(self, event):
        print(event.as_dict())

events = EventStream(exporter=JsonExporter())
```

`EventForwarder.forward()` reads at most 100 events from the source cursor,
sends them once, and persists only the contiguous acknowledged prefix. A
`FileEventCursorStore` is atomic and fenced across local processes, but a lost
remote response or cursor write can resend an accepted item. Partial delivery,
cursor expiry, malformed acknowledgements, transport errors, and cursor-save
errors are surfaced; the forwarder never retries in the background and makes no
exactly-once, remote-queue, or cross-forwarder ordering claim:

```python
from maple import (
    EventForwarder,
    EventStream,
    FileEventCursorStore,
    FileEventJournal,
    HttpEventBatchSender,
)

source = EventStream(
    max_events=1_000,
    journal=FileEventJournal(".maple-events", max_events=1_000),
)
forwarder = EventForwarder(
    source,
    HttpEventBatchSender(
        "https://collector.example/v1/events/batch",
        auth_token="collector-token",
        source_id="worker-a",
    ),
    FileEventCursorStore(".maple-event-forwarder"),
)
report = forwarder.forward()
```

For a host-owned local polling loop, wrap the forwarder explicitly. Construction
does not start a thread; `start()` owns one non-daemon worker and `stop()` uses
a bounded cooperative join. `run_once()` is available when the host owns the
polling lifecycle:

```python
from maple import EventForwarderScheduler

scheduler = EventForwarderScheduler(
    forwarder,
    interval_seconds=1.0,
    max_batches_per_tick=2,
)
started = scheduler.start()
if started.is_ok():
    stopped = scheduler.stop(timeout_seconds=10.0)
stats = scheduler.metrics()
```

Each tick performs at most `max_batches_per_tick` synchronous forward calls and
stops early when a report attempted no events. The scheduler does not retry,
persist a queue, coordinate multiple processes, or claim hosted
aggregation/exactly-once delivery. A blocked sender can cause a typed
stop-timeout result; the worker remains owned until it returns.

To suppress a repeated accepted batch at an authenticated receiver, configure
`RunServer(event_stream=..., event_deduplication_store=..., auth_token=...)`
with `InMemoryEventDeduplicationStore`. Keep the `source_id` stable across
forwarder restarts. The sender includes each source sequence; a matching
completed claim returns the previously redacted destination event without
publishing another one. Changed content for the same `(source_id, sequence)`
returns `EVENT_DEDUPLICATION_CONFLICT`, and a concurrent pending claim returns
`EVENT_DEDUPLICATION_IN_PROGRESS`.

The store is bounded by `max_entries` and finite `ttl_seconds`, retains only a
content digest plus redacted destination event, and is process-local. Eviction,
expiration, restart, and multiple receiver stores can allow duplicates again;
durable distributed deduplication and exactly-once side effects are not claimed.

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
is a local event contract with optional bounded local journal replay plus an
optional best-effort HTTP sink, not a durable broker, remote event log, or
hosted telemetry service. Provider-native `LLMChunk` streams can expose a bounded
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
subscriber/exporter/journal failures, and integer-millisecond publish latency totals,
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
Percentile latency histograms, durable replay, approval-replay correlation,
fleet aggregation, and hosted trace search remain host-owned or deferred.

## Evaluation and Provider Capabilities (preview)

The evaluation harness runs local runners against versioned golden cases. A
case can assert exact output, a bounded JSON schema, and an ordered tool
trajectory. `fixture_version` defaults to 1 and is reported with each result;
trajectory expectations are bounded to 256 tool names or structured steps.
Structured steps can include JSON-safe arguments, result, status, and duration;
actual values are redacted and size-bounded before they are returned. Failures
are recorded per case so one bad case does not abort the report.

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

For stronger trajectory fixtures, use `EvalTrajectoryStep`. The structured
trajectory can stand alone; when `tool_names` is also supplied, the names must
match the step order. Each step is bounded to 64 KiB and the trajectory to 256
steps. Reports and optional judges receive the redacted trajectory, while exact
fixture matching uses the validated host observation.

```python
from maple import EvalCase, EvalObservation, EvalTrajectoryStep, EvaluationHarness

case = EvalCase(
    case_id="lookup-trajectory-v1",
    input={"query": "MAPLE"},
    expected_trajectory=(
        EvalTrajectoryStep(
            "search",
            arguments={"query": "MAPLE"},
            result={"count": 1},
            status="ok",
        ),
    ),
)
report = EvaluationHarness().run(
    [case],
    lambda value: EvalObservation(
        output={"answer": "ready"},
        trajectory=(
            EvalTrajectoryStep(
                "search",
                arguments={"query": "MAPLE"},
                result={"count": 1},
            ),
        ),
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

Use `EvaluationHarness.run_async(...)` when the runner or judge is awaitable.
Both callbacks may also be synchronous. Cases run sequentially in fixture
order, and each runner result passes through the same deterministic checks,
redaction, and size bounds before the judge sees it. The judge receives the
redacted `EvalObservation`, including bounded tool names and trajectory, and
its pass/fail result contributes one additional check. No provider selection,
retry, calibration, raw-observation persistence, or hosted evaluation is
implied.

```python
import asyncio

from maple import EvalCase, EvalJudgeResult, EvalObservation, EvaluationHarness


async def evaluate():
    async def runner(value):
        return EvalObservation({"answer": "ready"}, ("search",))

    async def judge(fixture, observation):
        return EvalJudgeResult(score=0.9, passed=True)

    return await EvaluationHarness().run_async(
        [
            EvalCase(
                "async-lookup",
                {"query": "MAPLE"},
                output_schema={"type": "object", "required": ["answer"]},
                expected_tool_names=("search",),
            )
        ],
        runner,
        judge=judge,
    )


report = asyncio.run(evaluate())
```

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

### Native async provider completion (preview)

Async callers can use the same provider contract without changing message,
tool, usage, or typed-error handling:

```python
response = await provider.complete_async(
    messages,
    tools=tools,
    temperature=0.2,
    stop=["END"],
)
```

The built-in OpenAI-compatible and Anthropic adapters await their optional
native async SDK clients when available. If an installed SDK exposes only a
synchronous client, the adapter uses the base provider's explicit compatibility
fallback so existing integrations continue to work; MAPLE does not claim that
fallback is non-blocking. This boundary performs no implicit retry, provider
selection, or concurrent fan-out.

When a caller cannot accept that fallback, require a declaration from the
provider descriptor before creating it:

```python
requirements = ProviderRequirements(async_completion=True)
provider = router.create(configs, requirements)
```

The router matches this requirement only against
`ProviderCapabilities(async_completion=True)`. It does not inspect arbitrary
provider methods or infer non-blocking behavior from an inherited method.

### Multimodal image messages (preview)

`ChatMessage.content` accepts its existing string form or a bounded list of
text and `ImageContent` parts. Image sources must be HTTPS URLs or validated
base64 data URIs; MAPLE never fetches, decodes into executable content, or
otherwise executes an image source. The OpenAI-compatible adapter accepts both
source forms. The Anthropic adapter accepts base64 data URIs and fails closed
for remote URLs because it does not fetch them on MAPLE's behalf.

```python
import base64

from maple import ChatMessage, ChatRole, ImageContent

image = ImageContent(
    source="data:image/png;base64," + base64.b64encode(b"image-bytes").decode(),
    detail="high",
)
message = ChatMessage(
    role=ChatRole.USER,
    content=["Describe this image.", image],
)
```

Provider selection can make the requirement explicit. A provider descriptor
must declare `image_input=True`; providers that do not make that declaration
are not selected for the request:

```python
requirements = ProviderRequirements(image_input=True)
```

Image content is persisted in sessions and durable run checkpoints as bounded
JSON-safe `{type: "image", source, mime_type, detail}` data. Audio, video,
automatic image fetching, image generation, and provider-specific media
transcoding remain separate contracts.

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

### Composable sub-workflows

Register another `Workflow` as one bounded parent node with
`add_subworkflow(name, workflow, input_map=..., output_map=...)`. The optional
`input_map` maps parent state keys to child state keys, and `output_map` maps
child state keys back to parent state keys. Omitting a map copies the relevant
state with unchanged keys. Mapping keys must be strings of at most 256
characters, map destinations must be unique, and each map is capped at 256
entries.

```python
child = Workflow("summarize")
child.add_node("make", lambda ctx: {"summary": ctx.state["child_text"][:80]})
child.set_entry_point("make")
child.add_edge("make")

parent = Workflow("pipeline")
parent.add_subworkflow(
    "summary_step",
    child,
    input_map={"text": "child_text"},
    output_map={"summary": "summary"},
)
parent.set_entry_point("summary_step")
parent.add_edge("summary_step")
run = parent.run({"text": "A bounded workflow example."}, run_id="pipeline-1")
```

The child owns its configured checkpoint store. A deterministic child run ID
lets a parent resume an interrupted child and reuse a completed child after a
parent checkpoint or execution-journal recovery. A child pause is propagated
as a parent interruption with the child run ID and bounded payload. Missing
mapped keys and child execution/store failures are typed parent-node failures.
The local contract does not provide remote scheduling, distributed routing,
or exactly-once external effects; child handlers with external effects remain
at-least-once and must be idempotent.

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

### Bounded agent tool-result replay

Durable agent runs can reuse a successful result for a tool that explicitly
declares `replay_policy="reuse_success"`. Attach the same bounded execution
journal used by workflows:

```python
from maple import (
    FileAgentRunStore,
    FileExecutionJournal,
    TOOL_REPLAY_REUSE_SUCCESS,
    Tool,
)

agent.set_run_store(FileAgentRunStore("./.maple-runs"))
agent.set_execution_journal(FileExecutionJournal("./.maple-tool-replay"))
agent.register_tool(
    Tool(
        name="write_record",
        description="Write one record using the host-owned handler",
        parameters={"type": "object", "additionalProperties": True},
        handler=write_record,
        replay_policy=TOOL_REPLAY_REUSE_SUCCESS,
    )
)
```

The journal key is derived from the agent, durable run, reasoning step, tool
ordinal, tool name, and authorized JSON arguments. It does not include the
provider's tool-call ID, so a regenerated ID can reuse a matching saved
result. Only successful results are recorded; approval-required and human
input tools retain their existing ownership contracts. Journal records are
bounded and should be cleared with `execution_journal.clear(run_id)` after
retention is no longer required. Because result content is persisted, protect
the journal with the host's normal storage access controls and do not opt in
tools whose results cannot be retained.

This is an opt-in crash-window guard, not exactly-once execution. A process
failure after the handler returns but before the journal save can repeat the
external effect, and a journal write failure returns a typed error that warns
the effect may have occurred. Handlers that call external systems still need
idempotency keys or transactional coordination.

### Durable tool approvals

Approval-required autonomous tools can use a local durable approval store when
the host cannot provide a synchronous callback. The agent creates a bounded
pending request and never invokes the handler until the host records a decision
and consumes the approval.

When a durable approval is created while a local model `TraceSpan` is active,
the request persists bounded optional `trace_id` and `span_id` values. They
survive file-store restart and are included in the authenticated approval
inspection envelope. Pending tool errors carry the same fields, and normal
sync/async `tool.completed` events include the active model span plus the
pending approval ID when applicable. This is an observational local join:
prompts, arguments, results, hosted trace search, principal identity, and
exactly-once effects remain outside the contract.

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
`execute_approved_tool` claims the request before executing it. The built-in
in-memory and file stores then record one bounded terminal tool outcome, so a
second attempt or a durable run resume replays that outcome without invoking
the handler again. If the outcome cannot be recorded, the tool result is not
silently retried; a consumed request without a recorded outcome returns
`APPROVAL_OUTCOME_UNAVAILABLE` with an effect-uncertain signal. A custom store
without the optional `record_execution(...)` capability retains single-use
behavior. File persistence is atomic and thread-safe within one process, and
`FileApprovalStore` acquires a per-record `FileLeaseManager` fencing lease by default under
`<directory>/.maple-leases`. Pass `lease_manager=` to provide a caller-owned
manager or `lease_ttl_seconds=` to change the bounded 30-second default.
Failed acquisition returns `APPROVAL_LEASE_ERROR` without mutation; failed
release returns `APPROVAL_LEASE_RELEASE_ERROR` and means the mutation may
already be committed, so inspect the record before retrying. Approval arguments
may contain application-sensitive data and
should be protected with host filesystem access controls. The store does not
persist the full ReAct conversation or implement arbitrary request/response
HITL forms. Outcome recording is an at-least-once crash-window guard, not an
exactly-once side-effect protocol; a failure after the handler returns and
before the outcome write may leave the external effect uncertain and requires
host investigation or a new explicitly approved action.

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
summarization remain separate host/runtime decisions. The built-in stores also
implement the optional `SessionCompactionStore` contract for an explicit,
host-supplied summary:

```python
from maple import InMemorySessionStore, SessionMessage

store = InMemorySessionStore(max_messages=100)
created = store.create("chat-1")
store.append(
    "chat-1",
    SessionMessage(role="user", content="Earlier request"),
    expected_version=created.unwrap().version,
)
compacted = store.compact(
    "chat-1",
    "The earlier request asked for a bounded release summary.",
    keep_last=0,
    expected_version=1,
)
```

Compaction stores one bounded assistant summary and the requested recent tail
as one versioned mutation. It never calls an LLM or runs automatically;
invalid limits, stale versions, oversized summaries, and no-op requests fail
without mutation. The summary's provenance and any sensitive data retained in
the store remain host responsibilities.

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
replay, tool-result replay, automatic/token-aware compaction, authentication,
and cross-process turn leases remain separate capabilities.

### Bounded working-memory admission (preview)

`WorkingMemory` provides a small in-process context store with explicit
admission bounds. The constructor accepts `max_tokens` from `1` through
`1,000,000`. The store retains at most `4,096` entries. Keys must be
non-empty text without control characters and no more than `256` UTF-8 bytes;
content must be valid text encodable as UTF-8; and `relevance` must be a finite
number in the inclusive range `0..1`.

```python
from maple.autonomy import WorkingMemory

memory = WorkingMemory(max_tokens=8)
accepted = memory.add("task", "bounded context", relevance=0.8)
assert accepted.is_ok()

rejected = memory.add("too-large", "x" * 40)
assert rejected.is_err()
assert memory.get_context()[0]["key"] == "task"
```

Token usage is a deterministic local estimate: the ceiling of UTF-8 byte
length divided by four, with empty content using zero tokens. It is not a
provider tokenizer or billing estimate. When an accepted entry would exceed
the token budget or entry-count limit, the oldest entries are evicted until it
fits. An entry larger than the complete token budget is rejected before any
eviction or append. Invalid or rejected input leaves the existing context
unchanged.

`add()` returns stable typed errors: `MEMORY_KEY_INVALID`,
`MEMORY_CONTENT_INVALID`, `MEMORY_RELEVANCE_INVALID`, or
`MEMORY_ENTRY_TOO_LARGE`. Invalid `max_tokens` raises `ValueError`. The store
is not thread-safe; callers sharing an instance across threads must provide
external synchronization. This API does not summarize, persist, automatically
compact, or manage memory across processes.

`MemoryManager.summarize_and_archive(llm_provider=...)` also preserves the
working context until the generated summary has been persisted to episodic
memory. Provider failures and archive failures return their typed errors; an
archive failure does not clear or partially consume the working entries. A
successful archive returns the summary and then clears the working context.
The operation is not a cross-store transaction, so hosts should inspect the
returned error and decide whether to retry or retain the context.

### Bounded episodic memory admission (preview)

`EpisodicMemory` keeps a bounded event history for each task in the supplied
`StateStore`. The defaults retain at most `1,024` events per task and accept
serialized events up to `65,536` bytes. Both limits are configurable within
those maxima:

```python
from maple import EpisodicMemory, StateStore, StorageBackend

episodic = EpisodicMemory(
    StateStore(backend=StorageBackend.MEMORY),
    max_events_per_task=100,
    max_event_bytes=32_768,
)
stored = episodic.record("task-1", {"action": "search", "result": "found"})
assert stored.is_ok()
assert episodic.recall("task-1").unwrap()[0]["action"] == "search"
```

Task IDs must be non-empty text without Unicode control characters and at most
`256` UTF-8 bytes. Events must be mappings. Before the store is written, the
event plus its timestamp is encoded as bounded UTF-8 JSON with non-finite
numeric values rejected. An accepted event keeps the newest entries when the
per-task count is full. Invalid task IDs/events return
`EPISODIC_TASK_ID_INVALID` or `EPISODIC_EVENT_INVALID`; an event over the
configured byte bound returns `EPISODIC_EVENT_TOO_LARGE`; malformed stored
history returns `EPISODIC_STATE_INVALID`. Store read/write errors are
propagated. The bound is per task and per store instance, not a distributed
global quota, and this API does not add summarization, retry, or cross-store
transactions.

`search(query, limit=10)` accepts queries up to `4,096` UTF-8 bytes and result
limits from `1` through `1,000`. Invalid text returns
`EPISODIC_QUERY_INVALID`; an invalid limit returns
`EPISODIC_SEARCH_LIMIT_INVALID`. Search propagates state-store read/list
failures and returns `EPISODIC_STATE_INVALID` for malformed stored histories;
it never converts those failures into an empty successful result. Search is
keyword matching over the locally retained events, not semantic retrieval or
a distributed index.

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

### Workflow run HTTP transport

`WorkflowRegistry` and `RunServer` expose configured workflows to local tools
without adding an HTTP framework. Register workflows before starting the
server; the server binds to `127.0.0.1` by default and owns a daemon request
thread that `close()` shuts down. `RunClient` uses the same bounded contract
for local or separately hosted implementations.

```python
from maple import RunClient, RunServer, WorkflowRegistry

registry = WorkflowRegistry()
registry.register(workflow)

with RunServer(registry) as server:
    print(server.url)
    # POST /v1/workflows/<workflow>/runs
    # POST /v1/workflows/<workflow>/runs/<run_id>/resume
    # GET  /v1/workflows/<workflow>/runs/<run_id>

    client = RunClient(server.url)
    result = client.run("my-workflow", {"input": "MAPLE"})
    assert result.is_ok()
```

`GET /healthz` returns `{"status": "ok", "service":
"maple-run-server"}`. Run creation returns `201` and resume/inspection return
`200`; errors use `{"error": {"errorType": ..., "message": ...}}` with
`400`, `401`, `404`, `409`, `413`, `414`, or `500` status codes. Run bodies require
`application/json`; request and response bytes are bounded, and workflow
state/resume values still pass through the workflow JSON boundary. Set
`RunServer(auth_token="...")` to require `Authorization: Bearer ...` on every
route; unauthorized calls return `401`. `RunClient(auth_token="...")` sends
that header without putting credentials in the URL. The built-in server still
rejects non-loopback binding and does not provide TLS, token issuance,
multi-tenant authorization, streaming transport, or a hard sandbox. For a
single host-configured bearer principal, add `auth_principal=Principal(...)` to
enforce route scopes before request bodies are read:

```python
from maple import Principal, RunClient, RunServer

operator = Principal(
    "operator",
    ("health:read", "workflow:read", "workflow:invoke", "approval:decide"),
)
with RunServer(
    registry,
    auth_token="local-token",
    auth_principal=operator,
) as server:
    client = RunClient(server.url, auth_token="local-token")
```

Known route scope families are:

| Route family | Scope examples |
| --- | --- |
| Health | `health:read` |
| Workflows | `workflow:read`, `workflow:invoke` |
| Agents | `agent:read`, `agent:invoke`, `agent:resume`, `agent:cancel` |
| Approvals | `approval:read`, `approval:decide` |
| Human input | `interaction:read`, `interaction:write`, `interaction:consume` |
| Handoffs | `handoff:read`, `handoff:write` |
| Events | `event:read`, `event:publish` |

`Principal("operator", ("workflow:*",))` grants a scope family and
`Principal("operator", ("*",))` preserves the legacy all-routes behavior.
Missing scopes return `403` and the bounded request body is discarded. This is
a host-configured authorization policy, not token issuance, identity
verification, TLS, multi-tenant authorization, per-agent delivery, or a
hard-sandbox boundary. A remote deployment must supply those controls and
must not infer exactly-once effects from this transport.

When `RunServer` receives `human_input_store=...`, the same authenticated
contract exposes bounded human-in-the-loop control; configuring that store
requires `RunServer(auth_token="...")`. `RunClient` provides
`list_pending_human_input(limit)`, `get_human_input(id)`,
`respond_human_input(id, response, actor_id=...)`,
`reject_human_input(id, reason, actor_id=...)`,
`continue_human_input(id, prompt, input_schema, actor_id=...)`, and
`consume_human_input(id)`. These map to `/v1/interactions` routes and return
the store's JSON-safe request envelope. The server's existing request/response
limits apply, and the configured `HumanInputStore` remains authoritative for
schema validation, actor authorization, durable leases, notifications, and
one-time consumption. A server without a configured store returns `503` for
these routes. This is a loopback transport contract, not a hosted operator
service or automatic run scheduler.

When `approval_store=...` is configured, the same authenticated contract
exposes bounded approval control through `RunServer` and `RunClient`:

```python
from maple import InMemoryApprovalStore, RunClient, RunServer

approvals = InMemoryApprovalStore()
approvals.create(approval_request)

with RunServer(
    registry,
    approval_store=approvals,
    auth_token="approval-token",
) as server:
    client = RunClient(server.url, auth_token="approval-token")
    pending = client.list_pending_approvals(limit=25)
    inspected = client.get_approval(approval_request.approval_id)
    decided = client.decide_approval(
        approval_request.approval_id,
        approved=True,
        edited_arguments={"value": "operator-approved"},
    )
```

These calls map to `GET /v1/approvals/pending/<limit>`,
`GET /v1/approvals/<approval_id>`, and
`POST /v1/approvals/<approval_id>/decide`. The response is the bounded
JSON-safe `ApprovalRequest` envelope, including tool arguments and any recorded
terminal outcome; hosts must apply appropriate bearer-token scope, TLS,
retention, and sensitive-data controls. Invalid IDs, limits, decisions, and
edited arguments fail before mutation; missing stores return `503`, missing
records return `404`, and store conflicts preserve their typed `409` errors.
The route only records the decision. It does not consume or execute the
approval, retry a request, schedule a run, or provide hosted identity,
notifications, tenancy, or exactly-once effects.

### Agent run HTTP transport

`AgentRegistry` and `RunClient.run_agent(...)` provide a bounded, authenticated
one-way invocation seam for a host-owned agent handler. The handler receives a
task, copied JSON context, optional session ID, and request run ID, and returns
an `AgentRun` envelope:

```python
from maple import AgentRegistry, AgentRun, Result, RunClient, RunServer

agents = AgentRegistry()

def handler(task, context, *, session_id, run_id):
    return Result.ok(
        AgentRun(
            agent_id="researcher",
            run_id=run_id,
            status="completed",
            result={"task": task, "context": dict(context)},
        )
    )

agents.register("researcher", handler)

with RunServer(registry, agent_registry=agents, auth_token="local-token") as server:
    client = RunClient(server.url, auth_token="local-token")
    result = client.run_agent(
        "researcher", "find release notes", {"limit": 3}, session_id="s-1"
    )
    assert result.is_ok()
```

The route is `POST /v1/agents/<agent_id>/runs` and returns `201` with a
`{"run": {"agent_id": ..., "run_id": ..., "status": ..., "result": ...,
"error": ...}}` envelope. Invocation status is `completed`, `paused`, or
`failed`; a separately registered cancellation callback may return
`cancelled`.
Task text is limited to 8 KiB; IDs are limited to 256 UTF-8 bytes; context is
limited to 32 top-level keys, 128 items per object/array, depth 8, 8,192
characters per string, and 32 KiB serialized. Non-JSON handler results,
identity mismatches, malformed errors, and handler exceptions fail closed;
handler exception text is not returned. Attaching an `AgentRegistry` requires
a server bearer token. The client performs no retries, and the route provides
no remote persistence, cancellation, resume, scheduling, duplicate
suppression, or exactly-once side-effect guarantee. The host owns those
policies and must adapt asynchronous agents explicitly.

A host with an `AgentRunStore` can expose a bounded durable control plane by
passing `agent_run_store=...` and registering an explicit resume callback:

```python
from maple import AgentRun, InMemoryAgentRunStore, Result

run_store = InMemoryAgentRunStore()

def resume_handler(run_id):
    # Delegate to the same durable agent that owns this run_id.
    return Result.ok(AgentRun("researcher", run_id, "completed", {"ok": True}))

agents.register("researcher", handler, resume_handler=resume_handler)
with RunServer(
    registry,
    agent_registry=agents,
    agent_run_store=run_store,
    auth_token="local-token",
) as server:
    client = RunClient(server.url, auth_token="local-token")
    summary = client.inspect_agent_run("researcher", "run-1")
    resumed = client.resume_agent_run("researcher", "run-1")
```

`GET /v1/agents/<agent_id>/runs/<run_id>` returns the authoritative
checkpoint identity, status, counters, pending interaction IDs, session
correlation, usage, result/error, version, and timestamps. Messages and
reasoning steps are intentionally omitted. `POST
/v1/agents/<agent_id>/runs/<run_id>/resume` invokes only the explicitly
registered callback and returns the same `AgentRun` envelope as invocation.
`POST /v1/agents/<agent_id>/runs/<run_id>/cancel` invokes an explicitly
registered `cancel_handler` and requires a `cancelled` envelope. Missing
stores return `503`, cross-agent or missing runs return `404`, and missing
resume/cancel callbacks return `501`. Cancellation is cooperative; the host
remains responsible for token propagation, checkpoint mutation, cleanup,
retries, principal scopes, and exactly-once side-effect policy.

### Authenticated event transport

When `event_stream=...` is configured, `RunServer` exposes the existing
`EventStream` through `POST /v1/events`. Configuration requires a bearer token;
`RunClient.publish_event(event_type, payload, run_id=...)` sends one bounded
event at a time:

```python
from maple import EventStream, RunClient, RunServer

events = EventStream(max_events=1_000, max_payload_bytes=64_000)
with RunServer(registry, event_stream=events, auth_token="event-token") as server:
    client = RunClient(server.url, auth_token="event-token")
    published = client.publish_event(
        "agent.completed",
        {"status": "ok", "api_key": "redacted-at-the-boundary"},
        run_id="run-1",
    )
```

The endpoint also accepts the envelope emitted by `HttpEventExporter`; only
`event_type`, `payload`, and optional `run_id` are used. The host assigns the
receiving stream's sequence and timestamp, then applies the stream's redaction
and payload limits before retention, subscriber delivery, or exporter delivery.
Missing fields, malformed payloads, oversized bodies, and invalid event values
return typed `400` errors; an absent stream returns `503`. This is a bounded
authenticated ingestion seam for a host-owned stream, not durable remote
replay, fleet aggregation, or remote trace search.

For transport-efficient ingestion, `RunClient.publish_events(...)` and
`POST /v1/events/batch` accept 1–100 event envelopes. Events are submitted in
request order to the receiving stream. The response separates successful and
failed items while retaining each original zero-based index:

```python
batch = client.publish_events(
    [
        {"event_type": "agent.started", "payload": {"run_id": "run-1"}},
        {"event_type": "agent.completed", "payload": {"status": "ok"}},
    ]
)
if batch.is_ok():
    result = batch.unwrap()
    # {"published": [{"index": 0, "event": {...}}, ...], "failed": [...]}
```

Malformed batch structure, including an empty or over-100 item list, is
rejected before any event is attempted. Valid batches may partially succeed.
Without a configured deduplication store, callers own retry and idempotency
policy. With one, callers may pass a stable `source_id` and positive per-item
`sequence` values:

```python
events = client.publish_events(
    [{
        "sequence": 1,
        "event_type": "agent.completed",
        "payload": {"status": "ok"},
    }],
    source_id="worker-a",
)
```

The receiver acknowledges a matching completed source claim without publishing
a second event. Conflicting content and concurrent pending claims are typed
failures. Capacity, TTL, process restart, and downstream effects remain outside
the bounded in-memory deduplication contract.

For bounded remote inspection, use the same authenticated server with a
cursor-based read. `after` is the last sequence already processed and `limit`
is capped at `1,000` and at the stream's configured capacity:

```python
from maple import EventCursor, RunClient

cursor = EventCursor()
page = client.read_events(cursor, limit=25)
if page.is_ok():
    batch = page.unwrap()["batch"]
    events = batch["events"]
    next_cursor = EventCursor.from_dict(batch["next_cursor"]).unwrap()
```

This calls `GET /v1/events?after=<sequence>&limit=<limit>`. Returned events
are already redacted and include the receiver-assigned sequence/timestamp. A
cursor before the retained ring returns `EVENT_CURSOR_EXPIRED` with HTTP `409`
rather than silently skipping events; malformed, duplicate, unknown, negative,
or over-bound query values return typed `400` errors. The route reads the
host-owned in-memory bounded ring only. The route itself does not provide
durable replay, remote search, or fleet aggregation; use the local journal plus
`EventForwarder` for explicit bounded remote replay and aggregation.

### Handoff HTTP transport

When `handoff_store=...` is configured, `RunServer` exposes the existing
digest-only `HandoffStore` state machine through `RunClient`. Configuration
requires a server bearer token:

```python
from maple import HandoffRecord, InMemoryHandoffStore, RunClient, RunServer

handoffs = InMemoryHandoffStore()
record = HandoffRecord.pending(
    "handoff-1", "source", "target", "a" * 64, "b" * 64
)

with RunServer(registry, handoff_store=handoffs, auth_token="local-token") as server:
    client = RunClient(server.url, auth_token="local-token")
    created = client.create_handoff(record)
    accepted = client.accept_handoff("handoff-1", "target")
    completed = client.complete_handoff("handoff-1", "target", "goal-1")
    assert completed.is_ok()
```

The contract provides `create_handoff(record)`, `get_handoff(id)`,
`list_open_handoffs(limit)`, `accept_handoff(id, target_agent_id)`,
`complete_handoff(id, target_agent_id, target_goal_id)`, and
`fail_handoff(id, target_agent_id, error_type)`. Routes return digest-only
`HandoffRecord` envelopes; task and context contents are never transmitted.
The store remains authoritative for state, ownership, validation, and file
fencing. The bearer token authenticates transport access but does not create a
per-agent principal or authorization scope. Missing stores return `503`,
invalid records/limits return `400`, missing records return `404`, and state or
owner conflicts return `409`. No retries, queueing, notifications,
cancellation, scheduling, payload delivery, or exactly-once effect guarantee
is provided.

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
