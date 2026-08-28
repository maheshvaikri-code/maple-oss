<div align="center"> <img width="354" align="centre" height="174" alt="fulstretch" src="https://github.com/user-attachments/assets/e9eaf167-712f-448c-adf3-d55a0562cff7" /> </div>

# MAPLE - Multi Agent Protocol Language Engine

**Creator: Mahesh Vaijainthymala Krishnamoorthy (Mahesh Vaikri)**

<p>
<a href="https://github.com/maheshvaikri-code/maple-oss"><img src="https://img.shields.io/badge/version-1.1.3-brightgreen" alt="Version"></a>
<a href="https://github.com/maheshvaikri-code/maple-oss"><img src="https://img.shields.io/badge/Python-3.8%20|%203.9%20|%203.10%20|%203.11%20|%203.12%20|%203.13-brightgreen" alt="Python"></a>
<a href="https://github.com/maheshvaikri-code/maple-oss"><img src="https://img.shields.io/badge/Focused%20tests-240%20passed-brightgreen" alt="Focused tests"></a>
<a href="https://github.com/maheshvaikri-code/maple-oss/blob/main/LICENSE"><img src="https://img.shields.io/badge/License-AGPL%203.0-blue.svg" alt="License"></a>
<a href="https://mapleagent.org"><img src="https://img.shields.io/badge/Docs-mapleagent.org-blue" alt="Documentation"></a>
</p>

> The autonomous agentic AI framework with production-grade infrastructure. MAPLE combines LLM-powered autonomous agents with resource-aware messaging, type-safe error handling, cryptographic security, and distributed state — capabilities no other framework offers together.

---

## Why MAPLE

Most agent frameworks give you either **infrastructure** (messaging, security, fault tolerance) or **autonomy** (LLM reasoning, tool use, memory). MAPLE is the first to provide both in a single, cohesive framework.

|  | Infrastructure | Autonomy |
|---|---|---|
| **LangGraph / CrewAI / AutoGen** | Basic | Yes |
| **Google A2A / MCP / FIPA ACL** | Yes | No |
| **MAPLE** | **Yes** | **Yes** |

**What this means in practice:** Your autonomous agents get resource negotiation, circuit breakers, cryptographic link security, priority message queuing, distributed state, and fault-tolerant task scheduling — out of the box, not bolted on.

---

## Key Features

### Autonomous Agentic AI (v1.1.3)

- **ReAct Reasoning Loop** — Agents think, act, and reflect autonomously. Built-in backtracking when approaches fail.
- **Pluggable LLM Providers** — OpenAI, Anthropic Claude, or any compatible API (vLLM, Ollama, Together AI).
- **Multimodal Image Inputs (preview)** — Build bounded `ChatMessage` content from text and validated `ImageContent` parts. HTTPS image URLs work with OpenAI-compatible adapters; base64 data URIs work with both built-in adapters. MAPLE never fetches or executes image sources, and provider capability routing can require `image_input=True`.
- **Tool Framework** — Register custom tools with JSON Schema parameters or optional Pydantic-style input/output models. Built-in tools cover inter-agent communication, state read/write, resource checks, and secure link establishment.
- **Agent Handoff Tools (preview)** — Expose a specialist's bounded `pursue_goal` call as a normal model tool with approval-by-default, input bounds, structured target results, allowlisted bounded JSON context, async target support when explicitly declared, and optional local durable `pending → accepted → completed/failed` ownership records; this is local delegation, not remote routing or exactly-once effects.
- **Agent-as-Tool Delegation (preview)** — Let a manager agent invoke a specialist as a normal approval-by-default tool while retaining orchestration ownership; results are bounded to agent/goal/status/result, context is explicitly allowlisted, sync/async target contracts are supported, and remote routing, child-run replay, retries, and exactly-once effects remain outside the local boundary.
- **Guardrail Lifecycle Events (preview)** — Observe ordered `started`, `passed`, `rejected`, and `failed` input/output guardrail transitions through bounded metadata with local run/span correlation; guarded values, prompts, and raw callback errors never enter the event.
- **Bounded Serialization Formats** — JSON, restricted Pickle, optional MessagePack, and optional 1 MiB-bounded Protobuf envelopes for MAPLE JSON-compatible data; missing optional libraries fail explicitly.
- **Typed Contracts and Guardrails (preview)** — Validate bounded JSON or typed model inputs and outputs, request structured model responses, and fail closed on rejected or unavailable guardrails.
- **Bounded Structured-Output Repair (preview)** — Optionally give invalid typed/schema/guardrail output up to three correction attempts; retries remain inside reasoning and token budgets, with fail-fast behavior by default.
- **Trusted Local Execution (preview)** — Opt tools into bounded input/output, timeout, cooperative cancellation, approval, and concurrency controls; this is not an untrusted-code sandbox.
- **Retrieval/Data Primitives (preview)** — Ingest bounded documents through host-owned cursor connectors, split deterministic chunks, run local lexical or caller-supplied-vector retrieval, apply an optional provider-neutral reranker, retain source references for grounded answers, optionally resume through bounded in-memory or atomic file cursor checkpoints with revision fencing, and optionally apply a host-owned in-memory connector rate limit. Checkpointed ingestion is explicitly at-least-once at the sink boundary; rate limiting is fail-fast with no hidden sleep or retry.
- **Durable Agent Runs (preview)** — Opt synchronous or asynchronous ReAct goals into bounded in-memory or atomic file checkpoints with stable `run_id` recovery; file-backed run cursors use per-run cross-process fencing leases, pending durable approvals pause before further tool side effects, built-in approval stores replay bounded recorded terminal outcomes after a checkpoint crash window, and explicitly opted-in `Tool(replay_policy="reuse_success")` tools can reuse successful journaled results. Exactly-once external effects, host notifications, and sandboxing remain host-owned or unsupported.
- **Event Streaming and Redaction (preview)** — Publish bounded sequenced events with ring retention, cursor-based reads with explicit eviction errors, cooperative cancellation for waiters, wait/snapshot consumers, subscriber isolation, recursive credential redaction, provider request correlation in agent metadata, opt-in metadata-only `model.chunk` events from sync/async provider stream aggregation, optional atomic `FileEventJournal` restart replay of already-redacted events, optional `HttpEventExporter` delivery, and authenticated `RunServer`/`RunClient` single-event or bounded batch ingestion into a host-owned stream; `EventForwarder` adds explicit bounded remote aggregation with a durable cursor and at-least-once semantics, and `EventForwarderScheduler` adds opt-in bounded local polling with cooperative shutdown and metrics, while remote delivery remains bounded and cannot fail a run.
- **Bounded Remote Event Deduplication (preview)** — Opt an authenticated event receiver into `InMemoryEventDeduplicationStore`; `HttpEventBatchSender(source_id=...)` and `RunClient.publish_events(..., source_id=...)` carry bounded source IDs and source sequences so matching retries replay the existing redacted destination event, while conflicting or concurrent claims fail closed. Capacity, TTL, process restart, and multi-store boundaries remain explicit; durable distributed deduplication and exactly-once effects are not claimed.
- **Evaluation Harness (preview)** — Run versioned deterministic golden cases with output-schema checks, exact outputs, structured bounded tool trajectories, bounded reports, and redacted actual values; sync or async runners and host-supplied sync/async judges are supported sequentially without selecting a provider, retrying callbacks, or claiming semantic faithfulness.
- **Retrieval/Citation Evaluation (preview)** — Score lexical or vector retrieval against bounded golden source URIs with deterministic source-level precision, recall, and F1; generated-answer faithfulness remains a separate calibrated evaluation.
- **Grounded-Answer Evaluation (preview)** — Score bounded answer claims against supplied source text with deterministic lexical overlap and typed threshold failures; this is an explicit proxy, not semantic entailment or an LLM judge.
- **Capability-Aware Provider Fallback (preview)** — Select providers by declared tool/streaming/structured-output/context capabilities with deterministic initialization fallback.
- **Bounded Model Retry (preview)** — Opt-in sync/async retries for explicitly classified provider rate-limit, timeout, and transient failures with capped exponential backoff and metadata-only `model.retry_scheduled` events; authentication, validation, tool-side-effect replay, and remote scheduling remain fail-fast or host-owned.
- **Provider-Agnostic LLM Streaming (preview)** — Consume bounded text, tool-call, finish, usage-trailer, and request-correlation chunks through one async contract; OpenAI-compatible and Anthropic providers use native async streams when available, with a completion-backed fallback. `AutonomousConfig(stream_model_events=True)` reconstructs each streamed ReAct response and emits metadata-only `model.chunk` events; local publish-latency and subscriber/exporter failure metrics are available, while remote transport remains host-owned or a follow-on boundary.
- **Bounded Async Tool Fan-Out (preview)** — Execute independent tool calls concurrently within the per-step cap while preserving deterministic tool-message order and isolating worker failures.
- **Fail-Closed Tool Approval (preview)** — Approval-required tools never execute without an explicit callback or durable store decision; missing callbacks, callback failures, pending requests, and denials become typed tool results. Durable approvals support one bounded persisted argument edit before one-time consumption, retain bounded local `trace_id`/`span_id` correlation when created under a model span, emit approval-linked lifecycle metadata, built-in stores record and replay one bounded terminal outcome without re-running the handler, and file-backed approvals use per-record cross-process fencing leases; a missing outcome remains fail-closed and exactly-once effects remain outside this contract.
- **Durable Human Input (preview)** — Durable sync/async ReAct runs can call `request_human_input` to persist a bounded question/form, pause before later tool calls, validate a host response against JSON Schema, reject explicitly, and resume after restart. File-backed input records use per-record cross-process fencing leases; optional local host callbacks provide bounded lifecycle notifications and fail-closed actor authorization, and same-record follow-up rounds retain bounded history; remote interaction delivery remains outside this contract.
- **Bounded Conversation Sessions (preview)** — Persist JSON-safe turn messages in thread-safe in-memory or atomic file-backed stores with bounded quotas, immutable snapshots, and optimistic version conflicts; opt-in sync/async agent turns replay only stored user/assistant messages and surface post-run persistence errors.
- **Workflow Run HTTP Transport (preview)** — Expose registered workflows through a dependency-free bounded local HTTP server and call the same run/resume/inspection contract with `RunClient`; optional bearer authentication is available, while non-loopback binding, TLS, tenancy, streaming, and sandboxing remain host-owned.
- **Scoped Local Control Plane (preview)** — Attach a host-configured `Principal` with exact or family scopes to the authenticated `RunServer`; health, workflow, agent, approval, interaction, handoff, and event routes authorize before reading request bodies, while identity issuance, TLS, tenancy, and per-agent remote policy remain host-owned.
- **Bounded Agent-Run HTTP Transport (preview)** — Register host-owned synchronous agent handlers behind an authenticated `RunServer` and invoke them through `RunClient.run_agent(...)` with bounded task/context, session/run correlation, typed JSON-safe `AgentRun` envelopes, and exception redaction. Explicit `resume_handler` and `cancel_handler` callbacks plus `agent_run_store` add redacted durable inspection, resume, and cooperative cancellation; hard termination, scheduling, retries, principal scopes, and exactly-once effects remain host-owned.
- **Bounded Handoff HTTP Transport (preview)** — Expose an authenticated digest-only `HandoffStore` control plane through `RunServer`/`RunClient` for create, inspect, list, accept, complete, and fail transitions while preserving store-owned ownership and file-fencing semantics; raw task/context delivery, principal scopes, scheduling, retries, and exactly-once effects remain outside the contract.
- **Bounded Approval HTTP Transport (preview)** — Expose an authenticated `ApprovalStore` control plane through `RunServer`/`RunClient` for bounded pending-list, inspection, and approve/deny decisions with optional bounded edited arguments; the transport never consumes or executes an approval, and hosted identity, notifications, scheduling, tenancy, and exactly-once effects remain host-owned.
- **Bounded Event HTTP Transport (preview)** — Receive single events or 1–100 event batches through authenticated `RunServer`/`RunClient` routes into a host-owned `EventStream`, preserving local sequence, timestamp, redaction, retention-gap, and subscriber/exporter behavior; batch responses report indexed partial failures, local restart replay is available through the optional `FileEventJournal`, while fleet aggregation and remote trace search remain outside the contract.
- **Bounded Workflow Fan-Out/Fan-In (preview)** — Run independent workflow branches concurrently with isolated state snapshots, deterministic collision-free merging, checkpointed join boundaries, and durable bounded retry waves for failed branches.
- **Bounded Workflow Execution Journal (preview)** — Record normalized node outputs before checkpoint commits and recover persisted running checkpoints after a crash-window failure through deterministic execution keys and bounded in-memory or atomic file journals; arbitrary external side effects still require idempotent handlers.
- **Bounded Workflow Retry (preview)** — Configure capped exponential-backoff retries for ordinary nodes and parallel branches; retry counts, scheduled retry timestamps, and typed exhaustion are persisted in workflow checkpoints, while external effects remain at-least-once and require idempotent handlers.
- **Interop Envelope + Doctor CLI (preview)** — Strict adapter round-trip envelopes and a network-free `maple doctor --json` readiness report for the runtime surfaces.
- **Artifacts and Code Blocks (preview)** — Store immutable SHA-256-addressed files with bounded in-memory or file-backed stores, and extract Markdown code blocks as data without executing them.
- **Three-Tier Memory** — Working memory (context window), episodic memory (task history), semantic memory (learned facts). LLM-assisted summarization when context fills up.
- **Multi-Agent Orchestration** — Form teams by capability, execute via bounded parallel supervisor delegation or consensus voting with deterministic joins, and use async cancellation or total time budgets for request-scoped fan-out.
- **MCP Tool Discovery** — Discover live `tools/list` descriptors over bounded Streamable HTTP and use approved external tools as native MAPLE tools; the legacy URL-only helper remains offline for compatibility.
- **Observability** — Full decision traces with bounded provider correlation, optional thread-safe local `TraceSpan`/`SpanRecorder` model-step linkage, configurable stable span sampling, bounded local latency/status metrics with p50/p95/p99 views, optional bounded `HttpEventExporter` delivery, agent snapshots, and per-goal token usage tracking with optional hard budgets; hosted aggregation and remote trace search remain outside the local contract.
- **Workflow Runtime (preview)** — Define validated workflows with stable run IDs, JSON-safe node-boundary checkpoints, bounded fan-out/fan-in, interruption, conditional routing, local file-backed resume, bounded in-process history inspection, and opt-in crash-window output recovery.
- **Composable Sub-Workflows (preview)** — Register a bounded `Workflow` as a parent node with explicit parent-to-child and child-to-parent state maps; interrupted children resume through their own checkpoint store, and completed children can be reused after parent journal recovery. Remote scheduling, distributed routing, and exactly-once effects remain outside the local contract.

**Session Compaction (preview)** - Built-in session stores support an explicit host-supplied summary plus retained recent tail under optimistic version control. Compaction is bounded and provider-neutral; it never calls an LLM or runs automatically.

**Local Tool Spans (preview)** - When a `SpanRecorder` is attached, normal sync and async tool executions are recorded as bounded `agent.tool` child spans under the active model span. Arguments, results, and provider objects are not retained; optional stable sampling plus local retention, latency, and status metrics expose observability pressure.

**Remote Human-Input Transport (preview)** — When a `HumanInputStore` is
configured, the bounded authenticated `RunServer`/`RunClient` contract can
list, inspect, respond to, reject, continue, and consume durable interaction
records; configuring the store requires a server bearer token. Schema
validation, actor authorization, leases, notifications, and
one-time consumption remain store-owned; hosted identity, TLS termination,
automatic scheduling, and exactly-once effects remain outside the local
contract.

### Production Infrastructure

- **Result\<T,E\> Error Handling** — Rust-inspired type-safe results. No silent failures, no uncaught exceptions. Chain with `.map()`, `.and_then()`, `.map_err()`.
- **Resource-Aware Messaging** — Agents declare CPU, memory, and bandwidth requirements as first-class protocol features.
- **Link Identification Mechanism (LIM)** — Cryptographic channel verification using AES-256-GCM between agents.
- **Distributed State** — Shared state across agents with configurable consistency levels and change listeners.
- **Circuit Breakers & Retry** — Automatic failure detection, exponential backoff, and circuit breaker patterns.
- **Priority Message Queuing** — Messages routed by priority with health-aware routing.
- **Task Management** — Task queue, scheduler (capability matching + load balancing), fault-tolerant execution, result collection with 7 aggregation strategies.
- **Agent Discovery** — Auto-registration, capability matching, health monitoring, failure detection.
- **11 Protocol Adapters** — Native interop with A2A, MCP, FIPA ACL, AutoGen, CrewAI, LangGraph, OpenAI SDK, IBM ACP, S2.dev, n8n, plus a native doctrine profile.

### Explicit release boundaries

MAPLE fails closed for compatibility surfaces that are not implemented as
native runtime features: Redis state operations, mutual-TLS authentication,
and OAuth2 authentication currently return typed `NOT_IMPLEMENTED` results.
Local memory/file/SQLite state and the implemented JWT/API-key/certificate
trust-list paths remain distinct from those deferred integrations. Markdown
code blocks are extracted as data; `TrustedLocalExecutor` is for explicitly
trusted handlers and is not an untrusted-code sandbox.

### Doctrine Workforce (v1.1.2)

Primitives for running a governed multi-agent workforce (builders + fresh-context verifiers) as a runtime guarantee rather than a convention:

- **Fresh-Context Verifier Preset** — Separation of duties enforced by the broker: a per-agent **sender allowlist** (a verifier can be wired to reply only to the orchestrator, never to the builder it judges) plus an **artifact-ref-only payload policy** for guarded message types. `from maple.security import fresh_context_verifier_preset, SeparationOfDutiesPolicy, ArtifactRef`.
- **Doctrine Message Schemas** — Typed `WORK.PACKAGE` / `GATE.RESULT` builders and validators so a workforce speaks a checked vocabulary; payloads carry content-pinned artifact hashedrefs, not prose. `from maple.adapters.doctrine_adapter import DoctrineAdapter, build_work_package, build_gate_result`.
- **Token Budget as a Resource** — `tokens` is a first-class `ResourceRequest` type alongside `compute`/`memory`/`bandwidth`, so LLM budget maps to loop-engineering caps in negotiation.
- **Routability Check** — `broker.is_routable(agent_id)` and `agent.send(msg, require_routable=True)` distinguish "enqueued" from "deliverable" — a send to a nonexistent agent returns `Result.err(UNROUTABLE)` instead of a misleading `Ok`.
- **Exactly-Once Delivery** — Direct messages fire the receiver's handler exactly once; handler keys are normalized so a handler registered `"work.package"` receives an incoming `WORK.PACKAGE`.

### Resource & Reliability Primitives (v1.1.3)

Extensibility and hardening surfaced by integrating MAPLE into a governed downstream host:

- **Resource Lifecycles** — `ResourceManager` distinguishes **renewable** pools (returned on release) from **consumable** budgets (spent, never refunded — money, API calls, energy). `register_resource(type, amount, lifecycle=...)`; `release()` refunds only renewable resources.
- **Custom Resource Dimensions** — `ResourceRequest.custom` negotiates arbitrarily-named numeric resources (GPU, disk, `$` spend, QPS) without MAPLE hard-coding each.
- **Exclusive Leases** — `LeaseManager` / `Lease` grant in-memory exclusive, TTL-bounded holds with monotonic **fencing tokens**; `FileLeaseManager` adds atomic JSON persistence and OS-level cross-process locking for caller-owned local coordination. Expiry is the preemption mechanism; a crashed holder can't deadlock the resource. `from maple.resources import FileLeaseManager, LeaseManager`.
- **MCP Tool Governance** — `register_mcp_tools(..., policy=..., namespace=True, max_tools=...)` mediates the trust boundary for untrusted MCP servers: fail-closed authorization, server-namespacing to prevent tool shadowing, name sanitization, and a registration cap. Live-discovered tools are approval-required by default.
- **Bounded Backoff** — `exponential_backoff(max_delay=...)` caps per-attempt delay so a large retry count can't stall a caller holding a resource.
- **On-Demand Health** — `HealthMonitor.snapshot()` returns an immediate health read without waiting for the first sampling interval.

---

## Integrations

MAPLE ships with 11 adapters in `maple/adapters/` for bridging to external protocols and frameworks (10 external, plus a native doctrine profile).

| Adapter | File | What It Does |
|---------|------|-------------|
| **Google A2A** | `a2a_adapter.py` | Translate MAPLE messages to/from A2A Agent-to-Agent protocol. Maps MAPLE resources to A2A task metadata, bridges agent discovery via A2A Agent Cards. |
| **MCP** | `mcp_adapter.py` | Bridge Streamable HTTP MCP servers into MAPLE. Perform bounded initialization, live `tools/list` discovery, JSON-RPC `tools/call`, and register descriptors as approval-required native MAPLE `Tool` objects. |
| **FIPA ACL** | `fipa_acl_adapter.py` | Convert MAPLE messages to FIPA Agent Communication Language format. Supports performatives (inform, request, propose) and maps MAPLE priority to FIPA protocol fields. |
| **AutoGen** | `autogen_adapter.py` | Wrap MAPLE agents as AutoGen-compatible participants. Run AutoGen group chats backed by MAPLE's broker, security, and resource management. |
| **CrewAI** | `crewai_adapter.py` | Register MAPLE agents as CrewAI crew members. Map CrewAI tasks to MAPLE's task scheduler with fault tolerance and result collection. |
| **LangGraph** | `langgraph_adapter.py` | Expose MAPLE agents as LangGraph nodes. Run LangGraph state machines over MAPLE's message broker with distributed state sync. |
| **OpenAI SDK** | `openai_sdk_adapter.py` | Make MAPLE agents callable via OpenAI's Assistants/Chat API format. Translates tool calls and function results between OpenAI and MAPLE conventions. |
| **IBM ACP** | `acp_adapter.py` | Bridge to IBM Agent Communication Protocol. Maps MAPLE resource specifications to ACP capabilities and translates message formats. |
| **S2.dev** | `s2_adapter.py` | Durable streaming via [s2.dev](https://s2.dev). `S2Broker` provides persistent message delivery (per-agent and per-topic streams). `S2StateBackend` provides append-only state with full audit history. Install: `pip install maple-oss[s2]` |
| **n8n** | `n8n-integration/` | 3 visual workflow nodes (Agent, Coordinator, Resource Manager) for building multi-agent AI pipelines in [n8n](https://n8n.io) without code. |
| **Doctrine profile** | `doctrine_adapter.py` | Native, first-class `WORK.PACKAGE` / `GATE.RESULT` schemas — typed builders and validators for a governed workforce. Payloads carry artifact hashedrefs (via `ArtifactRef`), so they satisfy the fresh-context verifier preset. Imported explicitly, so `import maple` stays free of the security layer. |

All adapters follow MAPLE's `Result<T,E>` pattern and work with the existing security, resource, and broker infrastructure.

---

## Installation

```bash
pip install maple-oss
```

With LLM support (for autonomous agents):

```bash
pip install maple-oss[llm]
```

From source:

```bash
git clone https://github.com/maheshvaikri-code/maple-oss.git
cd maple-oss
pip install -e ".[llm]"
```

All optional dependency groups:

```bash
pip install maple-oss[llm]          # OpenAI + Anthropic providers
pip install maple-oss[s2]           # S2.dev durable streaming
pip install maple-oss[security]     # Cryptography + JWT
pip install maple-oss[performance]  # uvloop + orjson + msgpack
pip install maple-oss[dev]          # Testing + linting tools
```

Verify:

```bash
python -c "from maple import Agent, AutonomousAgent, Message, Config; print('MAPLE ready')"
```

---

## Quick Start

### 1. Basic Agent Communication

```python
from maple import Agent, Message, Priority, Config, SecurityConfig

# Create an agent
config = Config(
    agent_id="worker_agent",
    broker_url="memory://local",
    security=SecurityConfig(
        auth_type="token",
        credentials="secure_token",
        require_links=True
    )
)
agent = Agent(config)
agent.start()

# Send a typed message with Result<T,E>
message = Message(
    message_type="PROCESS_DATA",
    receiver="analysis_agent",
    priority=Priority.HIGH,
    payload={"task": "sentiment_analysis", "data": ["review_1", "review_2"]}
)

result = agent.send(message)
if result.is_ok():
    print(f"Sent: {result.unwrap()}")
else:
    print(f"Failed: {result.unwrap_err()['message']}")

agent.stop()
```

### 2. Autonomous Agent with Tools

```python
from maple import (
    Config, AutonomousAgent, AutonomousConfig,
    LLMConfig, Tool, Result,
)

# Define a custom tool
def calculator(expression: str = "") -> Result:
    allowed = set("0123456789+-*/.() ")
    if not all(c in allowed for c in expression):
        return Result.err({"error": "Only basic math allowed"})
    return Result.ok({"result": eval(expression)})

calc_tool = Tool(
    name="calculator",
    description="Evaluate a math expression like '2 + 3 * 4'",
    parameters={
        "type": "object",
        "properties": {
            "expression": {"type": "string", "description": "Math expression"},
        },
        "required": ["expression"],
    },
    handler=calculator,
)

# Create an autonomous agent
agent = AutonomousAgent(
    Config(agent_id="math-agent", broker_url="memory://local"),
    AutonomousConfig(
        llm=LLMConfig(provider="openai", model="gpt-4", api_key="sk-..."),
        max_reasoning_steps=10,
        max_total_tokens=12000,  # optional hard budget for this goal
    ),
)
agent.register_tool(calc_tool)

# Pursue a goal — the agent reasons, uses tools, and reflects
result = agent.pursue_goal("What is (15 * 37) + 42?")
if result.is_ok():
    goal = result.unwrap()
    print(f"Answer: {goal.result}")
    print(f"Reasoning steps: {len(goal.reasoning_trace)}")
```

### 3. Multi-Agent Team

```python
from maple import Config, AutonomousAgent, AutonomousConfig, LLMConfig
from maple.autonomy.orchestrator import AgentOrchestrator, TeamMember

# Create specialized agents
llm = LLMConfig(provider="openai", model="gpt-4", api_key="sk-...")

supervisor = AutonomousAgent(
    Config(agent_id="supervisor", broker_url="memory://local", capabilities=["planning"]),
    AutonomousConfig(llm=llm),
)
researcher = AutonomousAgent(
    Config(agent_id="researcher", broker_url="memory://local", capabilities=["research"]),
    AutonomousConfig(llm=llm),
)
coder = AutonomousAgent(
    Config(agent_id="coder", broker_url="memory://local", capabilities=["coding"]),
    AutonomousConfig(llm=llm),
)

# Form team and execute
orchestrator = AgentOrchestrator()
team_id = orchestrator.form_team("dev-team", members=[
    TeamMember(agent=supervisor, role="supervisor", capabilities=["planning"]),
    TeamMember(agent=researcher, role="worker", capabilities=["research"]),
    TeamMember(agent=coder, role="worker", capabilities=["coding"]),
]).unwrap()

# Supervisor decomposes goal, assigns sub-tasks to workers
result = orchestrator.execute_supervised(team_id, "Build a data processing pipeline")
```

### 4. Result\<T,E\> Error Handling

```python
from maple import Result

def process_data(data) -> Result:
    if not data:
        return Result.err({
            "errorType": "VALIDATION_ERROR",
            "message": "Empty data",
            "recoverable": True,
        })
    return Result.ok({"processed": len(data), "status": "complete"})

# Chain operations safely — no exceptions, no silent failures
result = (
    process_data(input_data)
    .map(lambda data: enrich(data))
    .and_then(lambda enriched: validate(enriched))
    .map_err(lambda err: log_error(err))
)
```

### 5. Resource-Aware Communication

```python
from maple.resources.specification import ResourceRequest, ResourceRange, TimeConstraint

request = ResourceRequest(
    compute=ResourceRange(min=4, preferred=8, max=16),
    memory=ResourceRange(min="8GB", preferred="16GB", max="32GB"),
    bandwidth=ResourceRange(min="100Mbps", preferred="1Gbps"),
    time=TimeConstraint(timeout="120s"),
    priority="HIGH",
)

message = Message(
    message_type="HEAVY_COMPUTATION",
    receiver="compute_agent",
    priority=Priority.HIGH,
    payload={"task": "train_model", "resources": request.to_dict()},
)
```

### 6. Secure Links (LIM)

```python
# Establish cryptographically verified communication channel
link_result = agent.establish_link("partner_agent", lifetime_seconds=3600)

if link_result.is_ok():
    link_id = link_result.unwrap()
    secure_msg = Message(
        message_type="SENSITIVE_DATA",
        receiver="partner_agent",
        payload={"data": "confidential"},
    ).with_link(link_id)
    agent.send_with_link(secure_msg, "partner_agent")
```

### 7. Distributed State

```python
from maple.state import StateStore, ConsistencyLevel

store = StateStore(consistency=ConsistencyLevel.STRONG)
store.set("mission_status", {"phase": "active", "agents": 5})

result = store.get("mission_status")
if result.is_ok():
    print(result.unwrap())

# Watch for changes
store.add_listener(lambda key, entry: print(f"Changed: {key}"))
```

### 8. Pub/Sub and Handlers

```python
# Register message handlers
@agent.handler("TASK_REQUEST")
def handle_task(message):
    print(f"Received task: {message.payload}")
    return Message(
        message_type="TASK_RESULT",
        receiver=message.sender,
        payload={"result": "done"},
    )

# Topic-based pub/sub
agent.subscribe("notifications")

@agent.topic_handler("notifications")
def handle_notification(message):
    print(f"Notification: {message.payload}")

# Publish to topic
agent.publish("notifications", Message(
    message_type="ALERT",
    payload={"level": "info", "text": "System healthy"},
))
```

---

## Architecture

```text
maple/
├── agent/            Agent lifecycle, config, message handlers, auto-registration
├── autonomy/         AutonomousAgent, ReAct loop, tools, memory, orchestrator, observability
├── broker/           Message routing (in-memory + NATS), priority queue, health-aware routing
├── core/             Message, Result<T,E>, type system, serialization
├── communication/    Streaming, pub/sub, request-response patterns
├── discovery/        Agent registry, capability matching, health monitoring, failure detection
├── error/            Circuit breaker, retry with backoff, error types and severity
├── llm/              LLM provider abstraction (OpenAI, Anthropic, compatible APIs)
├── resources/        Resource specification, allocation, negotiation
├── security/         Authentication, authorization, Link ID Mechanism, AES-256-GCM encryption
├── state/            Distributed state store, synchronization, consistency models
├── task_management/  Task queue, scheduler, fault tolerance, result collection, optimization
└── adapters/         A2A, MCP, FIPA ACL, AutoGen, CrewAI, LangGraph, OpenAI SDK, ACP, S2
```

### Autonomy Architecture

```text
┌─────────────────────────────────────────────────────┐
│                  AutonomousAgent                     │
│  ┌──────────┐  ┌──────────┐  ┌──────────────────┐  │
│  │ LLM      │  │ Tool     │  │ Memory           │  │
│  │ Provider  │  │ Registry │  │ (Working/Episodic│  │
│  │ (OpenAI/ │  │ (Custom +│  │  /Semantic)       │  │
│  │ Anthropic)│  │ Built-in)│  │                  │  │
│  └────┬─────┘  └────┬─────┘  └────────┬─────────┘  │
│       │              │                 │             │
│       └──────────────┼─────────────────┘             │
│                      │                               │
│              ┌───────▼───────┐                       │
│              │  ReAct Loop   │                       │
│              │ Think → Act → │                       │
│              │   Reflect     │                       │
│              └───────┬───────┘                       │
│                      │                               │
│  Inherits: Agent (messaging, security, resources)    │
└──────────────────────┼───────────────────────────────┘
                       │
          ┌────────────▼────────────┐
          │   AgentOrchestrator     │
          │  (Supervisor/Consensus) │
          └─────────────────────────┘
```

---

## How MAPLE Compares

MAPLE's comparison has two distinct dimensions: its native protocol and
infrastructure layer, and its still-maturing autonomous agent runtime. The
full functionality/code-block/runtime matrix is maintained in the
[Agent-Framework Parity Ledger](docs/agent-framework-parity.md) for LangGraph,
CrewAI, Microsoft Agent Framework, LlamaIndex, and OpenAI Agents SDK.

| MAPLE capability | Current release boundary |
|---|---|
| Resource negotiation, leases, broker routing, discovery, health, and priority queues | Native infrastructure |
| Result\<T,E\> errors, retries, circuit breakers, and cryptographic link security | Native infrastructure |
| ReAct agents, tools, typed contracts, retrieval, events, sessions, and local workflows | Native or preview; see the ledger for exact limits |
| Protocol interoperability | 11 adapters; adapters do not substitute for native runtime parity |
| Durable agent runs, broad HITL, remote handoff routing, sandboxing, hosted runtime, and multi-language SDKs | Partial, unsupported, or deferred; no parity claim is made |

---

## n8n Integration

MAPLE ships with first-class [n8n](https://n8n.io) integration — 3 visual workflow nodes for building multi-agent AI pipelines without code.

| Node | Purpose |
|------|---------|
| **MAPLE Agent** | LLM integration, smart processing, resource-aware execution |
| **MAPLE Coordinator** | Workflow orchestration, task distribution, result aggregation |
| **MAPLE Resource Manager** | Dynamic allocation, cost optimization, scaling |

Pre-built workflows included: AI Research Assistant, Content Creation Pipeline, Customer Service Bot.

See [n8n-integration/](n8n-integration/) for setup and usage.

---

## Testing

```bash
# Run all tests
python -m pytest tests/ -v

# Run with coverage
python -m pytest tests/ --cov=maple --cov-report=term-missing

# Run specific modules
python -m pytest tests/autonomy/ -v       # Autonomous agent tests
python -m pytest tests/llm/ -v            # LLM provider tests
python -m pytest tests/discovery/ -v      # Discovery tests
python -m pytest tests/task_management/ -v # Task management tests
python -m pytest tests/security/ -v       # Security tests
python -m pytest tests/broker/ -v         # Broker tests
```

Current status: the 101 tracked Python test files report **1,195 passed, 1
skipped in 222.53s**, with no warning output. The focused lifecycle slice
reports `10 passed in 0.27s`, the loopback server suite reports `4 passed in
2.34s`, and Ruff, Black, mypy, compile, doctor, and clean wheel/sdist/Twine
gates pass. The workspace Doctrine gold verifier and fresh review remain open;
coverage is not treated as a release gate until the complete release matrix is
clean.

---

## Examples

### Live MCP tools

Live discovery is explicit so a URL-only compatibility call never performs an
unexpected network request:

```python
from maple.adapters.mcp_adapter import MCPClient, StreamableHTTPTransport
from maple.autonomy import discover_mcp_tools, register_mcp_tools

transport = StreamableHTTPTransport("https://example.com/mcp")
client = MCPClient(agent, transport.server_url, transport=transport)
discovered = discover_mcp_tools(transport.server_url, agent, client=client)
if discovered.is_ok():
    register_mcp_tools(
        registry,
        discovered.unwrap(),
        server_id="example",
        namespace=True,
        policy=lambda tool, _server: tool.requires_approval,
    )
```

The transport enforces bounded request/response bodies and MCP initialization;
discovery rejects malformed or duplicate descriptors. The default URL-only
form preserves the historical two-tool offline compatibility behavior and is
not live discovery.

### MCP resource management

MCP resource actions can use MAPLE's existing allocation and negotiation
services when a host injects them into the adapter. The default remains
fail-closed, so an adapter never pretends to manage resources it does not own:

```python
import asyncio

from maple.adapters.mcp_adapter import MCPAdapter
from maple.resources import ResourceManager

manager = ResourceManager()
manager.register_resource("compute", 8)
adapter = MCPAdapter(agent, {}, resource_manager=manager)

allocated = asyncio.run(
    adapter.handle_mcp_tool_call(
        "maple_resource_management",
        {"action": "allocate", "resources": {"compute": {"min": 2}}},
    )
)
allocation_id = allocated.unwrap()["allocation"]["allocation_id"]

asyncio.run(
    adapter.handle_mcp_tool_call(
        "maple_resource_management",
        {"action": "release", "allocation_id": allocation_id},
    )
)
```

The `negotiate` action uses an injected `ResourceNegotiator` and requires
`agent_id`, `resources`, and an optional duration-string `timeout`. Calls are
validated at the MCP boundary and synchronous negotiation is moved off the
event loop. See [ADR-023](docs/adr/023-mcp-resource-management-boundary.md)
for the ownership and failure contract.

### Durable remote event forwarding

Hosts that need restartable delivery can combine a local bounded journal with
an authenticated batch destination. The forwarder advances its cursor only
through a contiguous acknowledged prefix; a lost response or cursor write may
cause a duplicate on the next explicit call, so this is at-least-once delivery
and not exactly-once effects:

```python
from maple import (
    EventForwarder,
    EventStream,
    FileEventCursorStore,
    FileEventJournal,
    HttpEventBatchSender,
    InMemoryEventDeduplicationStore,
)

events = EventStream(
    max_events=1_000,
    journal=FileEventJournal(".maple-events", max_events=1_000),
)
forwarder = EventForwarder(
    events,
    HttpEventBatchSender(
        "https://collector.example/v1/events/batch",
        auth_token="collector-token",
        source_id="worker-a",
    ),
    FileEventCursorStore(".maple-event-forwarder"),
)
report = forwarder.forward()
```

Each call sends at most 100 events and returns indexed published/failed
outcomes. Cursor expiry, malformed acknowledgements, transport failure, and
cursor persistence failure are surfaced rather than silently dropping events;
the forwarder performs no implicit retry or background scheduling. Hosts that
want a local polling loop can wrap it in `EventForwarderScheduler`, which uses
one owned non-daemon worker, one active tick, a finite interval, and a bounded
number of batches per tick. `run_once()` remains available for deterministic
host-controlled polling; a stop timeout is surfaced when a sender is still
blocking rather than pretending the worker was interrupted.

For a receiver that may see an accepted batch again after a lost response or
cursor write, configure `event_deduplication_store=...` on `RunServer` with an
authenticated `InMemoryEventDeduplicationStore`. The sender's `source_id` must
remain stable across restarts; each forwarded source sequence is then claimed
once within the store's capacity and TTL. A matching completed claim is
acknowledged without publishing a second destination event, while a conflicting
payload or concurrent pending claim fails closed. This is bounded in-memory
duplicate suppression only: process restart, eviction, multiple stores, and
downstream side effects remain outside the contract.

### Artifacts and code blocks

Code is treated as data until a separately approved isolation provider exists:

```python
from maple.autonomy import InMemoryArtifactStore, extract_code_blocks

blocks = extract_code_blocks(model_text).unwrap()
artifacts = InMemoryArtifactStore()
for block in blocks:
    artifact = artifacts.put(
        block.code.encode("utf-8"),
        name=f"block-{block.index}.txt",
        media_type="text/plain",
    ).unwrap()
    print(artifact.artifact_id, artifact.size)
```

The parser and stores enforce source, block, artifact, and total-store limits,
verify content hashes on reads, and reject path-like artifact names. They do
not run Python, shell, browser, or computer-use code.

| Example | Description |
|---------|-------------|
| [examples/hello_autonomous_agent.py](examples/hello_autonomous_agent.py) | Create an autonomous agent with custom tools, pursue a goal using ReAct |
| [examples/multi_agent_team.py](examples/multi_agent_team.py) | Form a team with supervisor + workers, execute goals, share memory |
| [example/helloworld.py](example/helloworld.py) | Basic agent communication hello world |
| [demo_package/](demo_package/) | Full demo suite with web dashboard and benchmarks |
| [demo/adapters_demo/](demo/adapters_demo/) | Protocol adapter performance comparison |
| [demo/autogen/](demo/autogen/) | AutoGen integration multi-agent coding team |

---

## Documentation

- [Getting Started](docs/getting-started.md) — Installation and first steps
- [API Reference](docs/api-reference.md) — Complete API documentation
- [Type System](docs/type-system.md) — MAPLE's rich type system
- [Protocol Specification](docs/Protocol_Language_Specification.txt) — Formal protocol definition
- [Protocol Comparison](docs/protocol-comparison.md) — Detailed comparison with A2A, MCP, FIPA ACL
- [Agent-Framework Parity Ledger](docs/agent-framework-parity.md) — Functionality and runtime gap analysis against five current agent frameworks
- [Result\<T,E\> Details](docs/details_Result_Type.md) — Deep dive into type-safe error handling
- [Best Practices](docs/best-practices.md) — Production deployment guidelines
- [Industry Applications](docs/industry-applications.md) — Real-world use cases
- [Troubleshooting](docs/troubleshooting.md) — Common issues and solutions
- [Changelog](CHANGELOG.md) — Version history

---

## Project Structure

```text
maple-oss/
├── maple/                   Core framework (70 Python modules)
│   ├── agent/               Agent lifecycle and configuration
│   ├── autonomy/            Autonomous agent, tools, memory, orchestrator
│   ├── broker/              Message routing and delivery
│   ├── core/                Message, Result<T,E>, types, serialization
│   ├── communication/       Streaming, pub/sub, request-response
│   ├── discovery/           Registry, capability matching, health monitoring
│   ├── error/               Circuit breaker, retry, error types
│   ├── llm/                 LLM provider abstraction layer
│   ├── resources/           Resource specification and negotiation
│   ├── security/            Auth, encryption, Link ID Mechanism
│   ├── state/               Distributed state management
│   ├── task_management/     Scheduling, fault tolerance, optimization
│   └── adapters/            10 protocol adapters
├── tests/                   1002 tests across all modules
├── docs/                    Comprehensive documentation
├── examples/                Autonomous agent and team examples
├── demo_package/            Interactive demos and web dashboard
├── n8n-integration/         Visual workflow nodes for n8n
├── pyproject.toml           Package configuration
├── setup.py                 Legacy setup script
└── VERSION                  Current version (1.1.3)
```

---

## Contributing

```bash
git clone https://github.com/maheshvaikri-code/maple-oss.git
cd maple-oss
pip install -e ".[dev,llm]"
python -m pytest tests/ -v
```

Contributions welcome in:

- Core protocol and infrastructure enhancements
- LLM provider implementations (Gemini, Mistral, Cohere, etc.)
- Tool ecosystem expansion
- Adapter implementations for new protocols
- Test coverage expansion
- Documentation improvements

---

## License

**MAPLE - Multi Agent Protocol Language Engine**
**Copyright (C) 2025 Mahesh Vaijainthymala Krishnamoorthy (Mahesh Vaikri)**

MAPLE is **dual-licensed**:

| Use case | License |
| --- | --- |
| Open source projects, research, personal use | [AGPL-3.0](LICENSE) — free |
| Proprietary software, SaaS, enterprise deployment | [Commercial License](COMMERCIAL_LICENSE.md) |

### Open Source (AGPL-3.0)

Free to use, modify, and distribute. If you run MAPLE as part of a network service, AGPL-3.0 requires you to make your application source code available to users of that service.

### Commercial License

If your organization builds proprietary products, deploys SaaS services, or has a policy against AGPL dependencies, a commercial license removes the copyleft obligation. Startup, Business, and Enterprise tiers available.

→ **[See COMMERCIAL_LICENSE.md](COMMERCIAL_LICENSE.md)** for tiers and pricing, or email **[maheshvaikri@gmail.com](mailto:maheshvaikri@gmail.com)** with subject `[MAPLE Commercial License]`.

---

**MAPLE - Multi Agent Protocol Language Engine**
**Creator: Mahesh Vaijainthymala Krishnamoorthy (Mahesh Vaikri)**

- Email: [mahesh@mapleagent.org](mailto:mahesh@mapleagent.org)
- GitHub: [github.com/maheshvaikri-code/maple-oss](https://github.com/maheshvaikri-code/maple-oss)
- Issues: [Report bugs or request features](https://github.com/maheshvaikri-code/maple-oss/issues)
- Website: [mapleagent.org](https://mapleagent.org)
