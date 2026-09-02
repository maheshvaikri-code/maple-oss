<div align="center">
  <img width="354" height="174" alt="MAPLE logo" src="https://github.com/user-attachments/assets/e9eaf167-712f-448c-adf3-d55a0562cff7" />
</div>

# MAPLE - Multi Agent Protocol Language Engine

**Creator: Mahesh Vaijainthymala Krishnamoorthy (Mahesh Vaikri)**

MAPLE is a Python multi-agent runtime and protocol layer. It combines
autonomous agent execution with typed messaging, resource-aware coordination,
durable local state, security boundaries, interoperability, and evaluation
tools.

- Release: 2.1.0; 2.0.0 is published on PyPI
- Python package: maple-oss
- License: [AGPL-3.0-only](LICENSE), with a [commercial license](COMMERCIAL_LICENSE.md) available
- Creator: Mahesh Vaijainthymala Krishnamoorthy (Mahesh Vaikri)

[![Version](https://img.shields.io/badge/version-2.1.0-brightgreen)](VERSION)
[![Python](https://img.shields.io/badge/Python-3.8%20%7C%203.9%20%7C%203.10%20%7C%203.11%20%7C%203.12-blue)](pyproject.toml)
[![CI](https://github.com/maheshvaikri-code/maple-oss/actions/workflows/ci.yml/badge.svg)](https://github.com/maheshvaikri-code/maple-oss/actions/workflows/ci.yml)
[![License](https://img.shields.io/badge/License-AGPL%203.0-blue.svg)](LICENSE)
[![Documentation](https://img.shields.io/badge/Docs-mapleagent.org-blue)](https://mapleagent.org)

> An agent can be clever and still be unreliable. MAPLE gives that agent a
> typed message, a bounded tool, a resource budget, a durable checkpoint, and
> an explainable result—so the host can decide what happens next.

MAPLE is the runtime beneath that story: a Python protocol layer for agents
that need to communicate, reason, recover, and remain governable. Version
2.0.0 brings the autonomy loop and the operational boundary into one coherent
local package while keeping hosted services and external side effects under
host control.

## Why MAPLE

An agent begins with a goal, but a dependable system begins with boundaries.
MAPLE connects those boundaries around the loop that turns intent into work:

`goal → model decision → validated tool → typed result → event/checkpoint`

That loop is useful on a laptop, inside a service, or as a building block in a
larger platform. The host still owns credentials, deployment, tenancy, and
external side effects; MAPLE makes the local contract explicit and testable.

The package provides:

- Result[T, E] values for explicit success and failure paths.
- Resource negotiation, lifecycle-aware budgets, priority routing, leases, and
  fencing tokens.
- Agent discovery, health monitoring, circuit breakers, retries, and task
  scheduling.
- Cryptographic link identification, authentication, authorization, bounded
  serialization, and redaction.
- Autonomous agents, typed tools, guardrails, memory, retrieval, workflows,
  sessions, durable local runs, events, and evaluation.

MAPLE has three related layers:

1. **Protocol:** typed messages, resource requirements, priorities, errors, and
   interoperability formats.
2. **Runtime:** brokers, discovery, state, leases, security, scheduling, and
   observability.
3. **Autonomy SDK:** ReAct agents, tools, model providers, workflows, memory,
   retrieval, approvals, handoffs, sessions, and evaluations.

## MAPLE 2.0.0 capability surface

The following is the shipped and tested local surface. **Preview** means a
bounded or opt-in contract that is ready for local integration and still
requires the host to supply policy, persistence, credentials, or operations.
It does not claim a hosted control plane or automatic distributed behavior.

### Agent execution and tools

- Synchronous and asynchronous ReAct-style agent loops with bounded reasoning
  and token budgets.
- OpenAI-compatible and Anthropic provider adapters, capability routing,
  native async completion when the optional SDK supports it, and explicit
  compatibility fallback otherwise.
- JSON Schema and typed tool contracts with bounded arguments/results,
  approval-by-default execution, structured-output repair, guardrails,
  cancellation tokens, timeouts, and concurrency limits.
- Agent handoffs and manager-style agent-as-tool delegation with bounded
  allowlisted context, local durable ownership records, optional local replay,
  and authenticated remote handoff payload delivery.
- Trusted local execution for host-supplied handlers. This is a bounded
  execution policy, not an untrusted-code sandbox.
- Markdown code-block extraction and content-addressed artifacts. Extracted
  code is data and is never executed by MAPLE.

### Workflows, sessions, memory, and human control

- Typed workflow nodes, conditional routing, bounded fan-out/fan-in,
  deterministic joins, composable sub-workflows, and per-node retry/backoff.
- Durable in-memory and file-backed agent-run checkpoints with stable run IDs,
  bounded history, CAS versions, fencing leases, and cooperative cancellation.
- Durable approval and human-input records, schema-validated responses,
  bounded follow-up rounds, actor authorization hooks, notification outboxes,
  and fail-closed resume behavior.
- Bounded working and episodic memory, fail-closed summary archiving, keyword
  search, conversation sessions, compaction, file persistence, and
  data-only version-based forking.
- Loopback RunServer/RunClient control-plane routes for bounded local
  workflow, agent, task, approval, interaction, event, handoff, and checkpoint
  operations with per-route authorization scopes.

### Retrieval, events, and evaluation

- Deterministic document chunking, source references, synchronous and
  asynchronous cursor ingestion, checkpointed ingestion, host-owned embedding
  providers, lexical retrieval, caller-supplied-vector retrieval, and an
  optional provider-neutral reranker.
- FileLexicalRetriever and FileVectorRetriever with bounded versioned JSON,
  atomic replacement, restart rebuilds, local instance refresh, and
  cross-process mutation fencing.
- Read-only retrieval/citation tools with bounded queries, top-k limits, source
  URI/title citations, output limits, and fail-closed backend/provider errors.
- Bounded sequenced event streams, cursor expiry, cooperative waiter
  cancellation, subscriber isolation, recursive credential redaction, provider
  correlation, local trace spans, journals, exporters, forwarding, and
  source-sequence deduplication.
- Deterministic evaluation for golden outputs, schemas, tool trajectories,
  retrieval/citation metrics, grounded-answer overlap, trace structure, judge
  calibration, and redacted bounded reports.

### Reliability and task management

- In-memory and file-backed task queues with bounded admission,
  ownership-safe lifecycle transitions, terminal history, at-least-once restart
  recovery, and a trusted one-shot local task worker.
- Authenticated remote task queue control for bounded submit, inspect, claim,
  start, heartbeat, complete, fail, cancel, retry, and statistics operations.
- Result[T, E], resource lifecycles, custom resource dimensions, priority
  routing, in-memory/file leases, discovery, health monitoring, retry/backoff,
  circuit breakers, and cryptographic link/security layers.

## Production infrastructure

MAPLE keeps the operational primitives close to the agent contract. A host can
start with an in-memory broker and move individual boundaries to files or an
injected transport as its deployment grows:

- **Typed failure handling** — `Result[T, E]` keeps validation, capacity,
  transport, and provider failures explicit and composable.
- **Resource-aware messaging** — CPU, memory, bandwidth, time, tokens, and
  caller-defined numeric dimensions travel with a request for negotiation.
- **Link and identity security** — cryptographic links, authentication,
  authorization scopes, token revocation, and recursive event redaction make
  security decisions visible at the boundary.
- **Reliability primitives** — priority queues, health-aware discovery,
  bounded retries, exponential backoff, circuit breakers, leases, and
  ownership-checked task transitions.
- **State and coordination** — local state stores, consistency policies,
  file-backed checkpoints, journals, cursor stores, and fencing leases support
  restartable single-host workflows.

### Explicit release boundaries

MAPLE fails closed for surfaces that are not native local runtime features.
Optional integrations such as Redis state operations, mutual-TLS
authentication, and OAuth2 currently return typed `NOT_IMPLEMENTED` results
where they are not configured. JWT, API-key, and certificate paths remain
separate local mechanisms. `TrustedLocalExecutor` accepts explicitly trusted
host handlers; it is not an untrusted-code sandbox.

### Resource and reliability primitives

`ResourceManager` distinguishes renewable capacity from consumable budgets.
`LeaseManager` and `FileLeaseManager` provide bounded holds with fencing tokens;
expiry is the recovery mechanism when a local holder crashes. `TaskQueue` and
`FileTaskQueue` preserve ownership checks and explicit at-least-once restart
semantics. Nothing in these local primitives silently upgrades an external
side effect to exactly once.

## Integrations and protocol boundaries

The Python package contains eleven adapter modules under `maple/adapters`. Each
one is a translation boundary, not a claim that an external runtime is bundled
inside MAPLE:

| Adapter | Module | Boundary |
| --- | --- | --- |
| Google A2A | `a2a_adapter.py` | Message and agent-card translation through the optional HTTP adapter. |
| MCP | `mcp_adapter.py` | Bounded Streamable HTTP initialization, live tool discovery, JSON-RPC calls, namespacing, and approval-aware registration. |
| FIPA ACL | `fipa_acl_adapter.py` | Performative and message translation. |
| AutoGen | `autogen_adapter.py` | Compatibility wrapper for participants and group chats. |
| CrewAI | `crewai_adapter.py` | Compatibility wrapper for crews and tasks. |
| LangGraph | `langgraph_adapter.py` | MAPLE-backed graph state and node integration. |
| OpenAI SDK | `openai_sdk_adapter.py` | OpenAI-compatible message and tool format translation. |
| IBM ACP | `acp_adapter.py` | ACP message and capability translation. |
| S2.dev | `s2_adapter.py` | Optional durable stream and state backend integration. |

The sibling [n8n integration](n8n-integration/README.md) provides TypeScript
nodes and sample workflows. Each adapter is a deliberately narrow translation
boundary: it maps messages, tools, or capabilities into MAPLE contracts while
leaving identity, credentials, and deployment with the host.

## Installation

The core package supports Python 3.8+.

~~~bash
python -m pip install maple-oss
python -m pip install "maple-oss[llm]"          # OpenAI and Anthropic SDKs
python -m pip install "maple-oss[security]"     # JWT and SSH crypto extras
python -m pip install "maple-oss[performance]"  # optional speedups
python -m pip install "maple-oss[adapters]"     # HTTP adapter dependency
python -m pip install "maple-oss[s2]"           # S2.dev integration
python -m pip install "maple-oss[dev]"          # test and quality tooling
~~~

For a source checkout:

~~~bash
git clone https://github.com/maheshvaikri-code/maple-oss.git
cd maple-oss
python -m pip install -e ".[dev,llm,security,adapters]"
~~~

Verify the installed package and offline doctor:

~~~bash
python -c "import maple; print(maple.__version__)"
python -m maple.cli doctor --json
~~~

## Quick Start

### Typed agent messaging

~~~python
from maple import Agent, Config, Message, Priority, Result

agent = Agent(Config(agent_id="worker", broker_url="memory://local"))
agent.start()
sent: Result = agent.send(
    Message(
        message_type="TASK_REQUEST",
        receiver="specialist",
        priority=Priority.HIGH,
        payload={"task": "summarize", "document_id": "doc-42"},
    )
)
if sent.is_ok():
    print("queued", sent.unwrap())
else:
    print("send failed", sent.unwrap_err())
agent.stop()
~~~

### Autonomous agent with a safe local tool

This example uses a small AST parser rather than evaluating model text as
Python. Credentials are read from the environment and are not placed in code.

~~~python
import ast
import operator
import os

from maple import AutonomousAgent, AutonomousConfig, Config, LLMConfig, Result, Tool

_OPS = {ast.Add: operator.add, ast.Mult: operator.mul}


def calculate(expression: str = "") -> Result:
    try:
        tree = ast.parse(expression, mode="eval").body
        if not isinstance(tree, ast.BinOp) or type(tree.op) not in _OPS:
            raise ValueError("only addition and multiplication are supported")
        if not all(
            isinstance(node, ast.Constant) and isinstance(node.value, int)
            for node in (tree.left, tree.right)
        ):
            raise ValueError("operands must be integers")
        return Result.ok(
            {"result": _OPS[type(tree.op)](tree.left.value, tree.right.value)}
        )
    except (SyntaxError, ValueError, TypeError, OverflowError) as error:
        return Result.err({"errorType": "VALIDATION_ERROR", "message": str(error)})


agent = AutonomousAgent(
    Config(agent_id="math-agent", broker_url="memory://local"),
    AutonomousConfig(
        llm=LLMConfig(
            provider="openai",
            model="gpt-4o-mini",
            api_key=os.environ["OPENAI_API_KEY"],
        ),
        max_reasoning_steps=8,
        max_total_tokens=8_000,
    ),
)
agent.register_tool(
    Tool(
        name="calculator",
        description="Calculate a small integer expression.",
        parameters={
            "type": "object",
            "properties": {"expression": {"type": "string"}},
            "required": ["expression"],
        },
        handler=calculate,
    )
)
~~~

### Multi-agent orchestration

Teams are explicit objects. A supervisor can decompose a goal while specialist
agents execute bounded work; the orchestrator returns typed per-member results
and preserves the host's control over model credentials and side effects.

~~~python
from maple import AutonomousAgent, AutonomousConfig, Config, LLMConfig
from maple.autonomy.orchestrator import AgentOrchestrator, TeamMember

llm = LLMConfig(
    provider="openai",
    model="gpt-4o-mini",
    api_key=os.environ["OPENAI_API_KEY"],
)
supervisor = AutonomousAgent(
    Config(agent_id="supervisor", broker_url="memory://local"),
    AutonomousConfig(llm=llm, max_reasoning_steps=6),
)
researcher = AutonomousAgent(
    Config(agent_id="researcher", broker_url="memory://local"),
    AutonomousConfig(llm=llm, max_reasoning_steps=6),
)
orchestrator = AgentOrchestrator(max_parallel_agents=2)
team_id = orchestrator.form_team(
    "review-team",
    [
        TeamMember(supervisor, role="supervisor", capabilities=["planning"]),
        TeamMember(researcher, role="worker", capabilities=["research"]),
    ],
).unwrap()
result = orchestrator.execute_supervised(team_id, "Review the approved report")
~~~

### Secure links, state, and pub/sub

For message-level protection, construct the agent with a host-owned
`SecurityConfig`, establish a bounded link, and attach that link to the message.
State stores expose versioned reads and updates; the broker also supports topic
subscriptions for notifications that do not need request/response semantics.

~~~python
import os

from maple import Config, Message, Priority, SecurityConfig
from maple import Agent
from maple.state import ConsistencyLevel, StateStore

agent = Agent(
    Config(
        agent_id="secure-worker",
        broker_url="memory://local",
        security=SecurityConfig(
            auth_type="token",
            credentials=os.environ["MAPLE_AGENT_TOKEN"],
            require_links=True,
        ),
    )
)
link = agent.establish_link("specialist", lifetime_seconds=3_600).unwrap()
secure_message = Message(
    message_type="SENSITIVE_DATA",
    receiver="specialist",
    priority=Priority.HIGH,
    payload={"status": "ready"},
).with_link(link)
agent.send_with_link(secure_message, "specialist")

state = StateStore(consistency=ConsistencyLevel.STRONG)
state.set("mission_status", {"phase": "active"}).unwrap()
print(state.get("mission_status").unwrap())
~~~

The link handshake is a protocol boundary, not a replacement for TLS or host
identity management. Hosts remain responsible for secret rotation, trust roots,
network exposure, and authorization policy.

### Explicit authentication configuration

JWT support is intentionally fail-closed. MAPLE never invents a signing key:
the host must provide a secret through a secret manager or environment
variable, and the secret must contain at least 32 UTF-8 bytes. A missing or
short secret returns a typed `JWT_SECRET_NOT_CONFIGURED` result.

~~~python
import os

from maple.security import AuthenticationConfig, AuthenticationManager

auth = AuthenticationManager(
    AuthenticationConfig(jwt_secret=os.environ["MAPLE_JWT_SECRET"])
)
issued = auth.generate_jwt(
    principal="worker-agent",
    permissions=["tasks:read", "tasks:write"],
    expires_in=3_600,
)
if issued.is_ok():
    verified = auth.verify_token(issued.unwrap())
    print(verified.unwrap().principal)
~~~

The configuration object keeps policy visible at the call site. Hosts should
rotate secrets outside the process, avoid logging tokens, and treat revocation
as a deny decision: a revoked token cannot be authenticated again.

### Typed failures and resource budgets

MAPLE uses `Result[T, E]` at important boundaries. A caller can compose work
without turning expected validation, capacity, or transport failures into
unstructured exceptions. Resource requests carry the budget alongside the
message so the receiving host can accept, reject, or negotiate it.

~~~python
from maple import Message, Priority, Result
from maple.resources import ResourceRange, ResourceRequest, TimeConstraint

request = ResourceRequest(
    compute=ResourceRange(min=2, preferred=4, max=8),
    memory=ResourceRange(min="2GB", preferred="4GB", max="8GB"),
    time=TimeConstraint(timeout="120s"),
    priority="HIGH",
)

message = Message(
    message_type="INDEX_DOCUMENTS",
    receiver="retrieval-worker",
    priority=Priority.HIGH,
    payload={"document_id": "doc-42", "resources": request.to_dict()},
)

def accept(result: Result) -> str:
    if result.is_err():
        return f"rejected: {result.unwrap_err()}"
    return f"accepted: {result.unwrap()}"
~~~

### Durable local queues and workflows

Use the in-memory queue while shaping a system, then move to
`FileTaskQueue` or a host-owned remote control plane when restart behavior is
part of the deployment contract. Queue transitions are ownership-checked and
bounded; restart recovery is explicitly at-least-once.

~~~python
from maple.task_management import TaskPriority, TaskQueue

queue = TaskQueue(max_queue_size=100)
submitted = queue.submit_task(
    "summarize",
    {"document_id": "doc-42"},
    priority=TaskPriority.HIGH,
)
task_id = submitted.unwrap()
queue.assign_task(task_id, "worker-agent").unwrap()
queue.start_task(task_id, "worker-agent").unwrap()
queue.complete_task(task_id, "worker-agent", {"status": "done"}).unwrap()
~~~

For stateful branches, a `Workflow` gives each node a read-only context and
commits bounded JSON state at node boundaries. The same model supports
conditional routing, bounded fan-out/fan-in, retry policies, checkpoint
stores, and explicit resume.

~~~python
from maple import Workflow

workflow = Workflow("normalize-document")
workflow.add_node(
    "normalize",
    lambda context: {"text": context.state["text"].strip().lower()},
).unwrap()
workflow.set_entry_point("normalize").unwrap()
workflow.add_edge("normalize", None).unwrap()

run = workflow.run({"text": "  Hello MAPLE  "}).unwrap()
assert run.status == "completed"
~~~

### Memory, retrieval, and citations

Working memory is bounded admission, not an unbounded transcript. Retrieval
keeps source references attached to results so an application can decide how
to cite or display them. Embedding generation and corpus authorization remain
host-owned.

~~~python
from maple import Document, InMemoryLexicalRetriever, SourceRef
from maple.autonomy import WorkingMemory

memory = WorkingMemory(max_tokens=2_048)
memory.add("mission", "The worker is indexing the approved corpus.")

retriever = InMemoryLexicalRetriever()
retriever.add_document(
    Document(
        document_id="doc-42",
        text="MAPLE keeps source references with retrieval results.",
        source=SourceRef(uri="https://example.test/doc-42", title="MAPLE note"),
    )
).unwrap()
hits = retriever.search("source references", top_k=3).unwrap()
print(hits[0].chunk.source.uri)
~~~

For restartable local search, replace the in-memory retriever with
`FileLexicalRetriever` or `FileVectorRetriever`. Both use bounded versioned
JSON, atomic replacement, and local fencing. A vector retriever accepts
caller-supplied embeddings; it does not call a model or a managed vector
service on your behalf.

### Sessions, events, and code blocks

Conversation sessions store JSON-safe turns with optimistic versions and
data-only forking. Event streams retain a bounded, redacted window and expose
cursor-based reads. Code-block extraction creates content-addressed artifacts;
it never executes model-produced Python, shell, browser, or computer-use code.

~~~python
from maple import EventStream, InMemorySessionStore, SessionMessage

sessions = InMemorySessionStore()
session = sessions.create("case-42").unwrap()
session = sessions.append(
    session.session_id,
    SessionMessage(role="user", content="Summarize the approved report."),
    expected_version=session.version,
).unwrap()

events = EventStream(max_events=100)
events.publish(
    "session.message.accepted",
    {"session_id": session.session_id, "status": "stored"},
    run_id="run-42",
).unwrap()
batch = events.read(limit=10).unwrap()
print(batch.events[0].event_type)
~~~

The durable variants (`FileSessionStore`, `FileEventJournal`, and the local
run/checkpoint stores) are suitable for one host or a shared local filesystem.
They do not claim distributed consensus, exactly-once external effects, or
automatic background scheduling.

### Code blocks remain data

~~~python
from maple.autonomy import InMemoryArtifactStore, extract_code_blocks, materialize_code_block

model_text = "```python\nprint('stored as data')\n```"
blocks = extract_code_blocks(model_text).unwrap()
store = InMemoryArtifactStore()
for block in blocks:
    artifact = materialize_code_block(store, block).unwrap()
    print(artifact.artifact_id, artifact.size)
~~~

The artifact boundary validates sizes, names, UTF-8 bytes, and SHA-256
identity. It does not run Python, shell, browser, or computer-use code.

## Architecture

MAPLE is intentionally layered so a host can adopt the smallest useful
surface first:

~~~text
maple/
├── core/             Message, Result[T, E], serialization, and type contracts
├── agent/            Agent lifecycle, configuration, handlers, and routing
├── autonomy/         ReAct loops, tools, memory, retrieval, runs, events, and workflows
├── broker/           In-memory and optional broker-backed message delivery
├── discovery/        Agent registry, capabilities, health, and failure detection
├── resources/        Resource ranges, allocation, negotiation, and local leases
├── security/         Authentication, authorization, cryptographic links, and redaction
├── state/            State stores, consistency, and synchronization
├── task_management/  Bounded queues, scheduling, workers, and result collection
└── adapters/         A2A, MCP, FIPA ACL, ACP, S2.dev, and ecosystem translations
~~~

The autonomy loop sits above the protocol/runtime layer:

~~~text
goal
  │
  ▼
model provider ──► validated tool ──► typed Result[T, E]
  │                                      │
  └────────────── event + checkpoint ◄───┘
                         │
                         ▼
                    host decision
~~~

This shape makes the important transitions inspectable. A tool can be
approved before execution, a failure can be returned as data, a run can be
checkpointed before a later side effect, and an event can be redacted before
it reaches a subscriber or exporter.

## Operational boundaries

MAPLE supplies local contracts. The application or platform hosting MAPLE
supplies the environment around them:

| Host responsibility | MAPLE's local contribution |
| --- | --- |
| Secret storage and rotation | Explicit authentication configuration and token lifecycle |
| Model credentials and provider choice | Provider interfaces, capability checks, and typed failures |
| Authorization policy and tenancy | Scoped local control-plane routes and host policy hooks |
| External side effects | Approval, bounded tools, cancellation signals, and durable records |
| Deployment, TLS, and network exposure | Loopback transport with bounded requests and responses |
| Distributed coordination | Local file fencing, version checks, and clear at-least-once boundaries |
| Untrusted-code isolation | Trusted host handlers only; MAPLE is not a sandbox |

Keeping this boundary visible is part of using MAPLE correctly. Local
durability is useful without pretending to be a hosted service, and an adapter
is useful without silently changing who owns identity or side effects.

### Configuration is honored or refused

Two rules follow from the same principle — a configuration MAPLE cannot
honor is reported, never quietly substituted
([ADR-157](docs/adr/157-broker-configuration-fidelity-and-fail-closed-transport.md)):

- A `nats://` or `s2://` `broker_url` whose driver is not installed raises
  `BrokerUnavailableError` at agent construction. It does not fall back to the
  in-memory broker, because an agent that reports successful sends into a
  process-local bus is worse than one that fails to start.
- `require_links=True` is enforced. If the broker cannot build a link manager,
  link-enforced sends raise `SecurityError` rather than proceeding
  unenforced — a security control that cannot run refuses.

`import maple` has no global side effects; it does not construct an agent or a
broker.

## n8n companion integration

The repository also contains a separate TypeScript integration for visual
workflows. It provides MAPLE Agent, MAPLE Coordinator, and MAPLE Resource
Manager nodes plus sample workflows. The integration is not part of the
Python wheel or source distribution and has its own Node/npm validation loop.

~~~bash
cd n8n-integration
npm install
npm run validate
~~~

The node package submits work to a host; it does not provide hosted MAPLE,
credential storage, tenancy, or deployment by itself. See the
[integration README](n8n-integration/README.md) for node fields and sample
workflows.

| Node | Purpose |
| --- | --- |
| **MAPLE Agent** | Submit bounded agent work to a configured MAPLE host. |
| **MAPLE Coordinator** | Orchestrate workflow steps and collect typed results. |
| **MAPLE Resource Manager** | Surface resource-aware allocation in a visual flow. |

The included workflows are starting points for research, content, and
customer-service automations. They remain host integrations: credentials,
network policy, deployment, and external effects are configured outside the
Python runtime.

## Examples and companion integrations

- [Examples](examples/README.md) - small core and autonomy examples.
- [External demo package](demo_package/README.md) - interactive demos; not
  included in the core wheel or sdist.
- [n8n integration](n8n-integration/README.md) - TypeScript nodes and sample
  workflows; not included in the Python distribution.
- [Launch materials](LAUNCH/README.md) - local launch/demo helpers and their
  publication boundary.

## Testing and quality

~~~bash
python -m pytest tests/ -q
python -m pytest tests/security/ -q
python -m pytest tests/autonomy/ -q
python -m pytest tests/task_management/ -q
python -m pytest tests/broker/ -q
python -m pytest tests/ --cov=maple --cov-report=term-missing
python -m black --check maple
python -m isort --check-only maple
python -m flake8 maple/ --max-line-length=88
python -m compileall -q maple
python -m maple.cli doctor --json
~~~

The final local release-equivalent run completed with **1,936 passed and 1
skipped**. The full suite is the release gate; focused suites are useful while
iterating on a boundary. The offline doctor checks core, evaluation, events,
execution, interop, retrieval, server, and session readiness without making a
network request. Re-run the commands above on the exact checkout before
publishing; no evidence in this README authorizes publication. See the
[release QA record](docs/qa/maple-agent-runtime-release-2.0.0.md) and
[ultra-review record](docs/reviews/maple-ultra-review-2.0.0.md).

## Release and website status

MAPLE 2.0.0 is published on PyPI (`maple_oss-2.0.0`, uploaded 2026-08-31) and
tagged as a GitHub Release with source and wheel artifacts. 2.1.0 is prepared
but not yet published; see the changelog for its behavior-breaking fixes.

The website is intentionally **in standing**: tracked static assets are held
for a later copy/link/accessibility pass and deployment decision. See
[website/README.md](website/README.md) and the
[external-phase plan](docs/plans/maple-publication-website-cloud-registry.md).

## Documentation map

- [Getting started](docs/getting-started.md)
- [API reference](docs/api-reference.md)
- [Protocol specification](docs/Protocol_Language_Specification.txt)
- [Protocol comparison](docs/protocol-comparison.md)
- [Type system](docs/type-system.md)
- [Best practices](docs/best-practices.md)
- [Troubleshooting](docs/troubleshooting.md)
- [Changelog](CHANGELOG.md)
- [2.0.0 release checklist](docs/releases/v2.0.0.md)

## Project structure

~~~text
maple-oss/
├── maple/                 Python runtime and public package
├── docs/                  specifications, ADRs, plans, reviews, and QA records
├── tests/                 Python regression and contract tests
├── examples/              supported examples
├── demo/                  adapter-focused demonstrations
├── demo_package/          external interactive demo package
├── n8n-integration/       companion TypeScript integration
├── website/               held static website assets and website notes
├── pyproject.toml         package metadata and optional dependencies
├── VERSION                Python package version
└── CHANGELOG.md           release history
~~~

## Contributing

~~~bash
python -m pip install -e ".[dev,llm,security,adapters]"
python -m pytest tests/ -q
~~~

Keep behavior changes covered by tests, preserve local versus hosted
boundaries, and update the relevant docs, changelog, and review/QA artifact.

## License and attribution

MAPLE is Copyright (C) 2025 Mahesh Vaijainthymala Krishnamoorthy (Mahesh
Vaikri). The core project is licensed under the [GNU Affero General Public
License, version 3](LICENSE). Proprietary use may require the separate
[commercial license](COMMERCIAL_LICENSE.md).

- GitHub: <https://github.com/maheshvaikri-code/maple-oss>
- Issues: <https://github.com/maheshvaikri-code/maple-oss/issues>
- Documentation site: <https://mapleagent.org>
