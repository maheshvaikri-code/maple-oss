# MAPLE - Multi Agent Protocol Language Engine

MAPLE is a Python multi-agent runtime and protocol layer. It combines
autonomous agent execution with typed messaging, resource-aware coordination,
durable local state, security boundaries, interoperability, and evaluation
tools.

- Release: 2.0.0 local release candidate (not published)
- Python package: maple-oss
- License: [AGPL-3.0-only](LICENSE), with a [commercial license](COMMERCIAL_LICENSE.md) available
- Creator: Mahesh Vaijainthymala Krishnamoorthy (Mahesh Vaikri)

[![Version](https://img.shields.io/badge/version-2.0.0-brightgreen)](VERSION)
[![Python](https://img.shields.io/badge/Python-3.8%2B-blue)](pyproject.toml)
[![License](https://img.shields.io/badge/License-AGPL%203.0-blue.svg)](LICENSE)

> MAPLE is designed for hosts that need an agent loop and a reliability
> boundary in the same runtime. The release makes local, bounded contracts
> explicit; it does not imply hosted services, sandboxing, or exactly-once
> effects.

## Why MAPLE

Agent frameworks commonly focus on reasoning and orchestration. MAPLE also
provides protocol and runtime primitives that a production host normally has
to assemble separately:

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

The following is the shipped and tested local surface. Items marked
**preview** in the parity ledger are bounded or opt-in contracts; they are not
claims of a hosted service or distributed control plane.

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

## Protocol and framework interoperability

The Python package contains ten adapter modules under maple/adapters:

| Adapter | Surface |
| --- | --- |
| Google A2A | Message and agent-card translation through the optional HTTP adapter. |
| MCP | Bounded Streamable HTTP initialization, live tool discovery, JSON-RPC calls, namespacing, and approval-aware registration. |
| FIPA ACL | Performative and message translation. |
| AutoGen | Compatibility wrapper for AutoGen participants and group chats. |
| CrewAI | Compatibility wrapper for crews and tasks. |
| LangGraph | MAPLE-backed graph state and node integration. |
| OpenAI SDK | OpenAI-compatible message and tool format translation. |
| IBM ACP | ACP message and capability translation. |
| S2.dev | Optional durable stream and state backend integration. |
| Doctrine profile | Typed WORK.PACKAGE and GATE.RESULT contracts for governed agent workforces. |

The sibling [n8n integration](n8n-integration/README.md) provides TypeScript
nodes and sample workflows. An adapter is an interoperability boundary; it
does not make MAPLE natively equivalent to the external framework.

## Framework parity boundary

The [Agent-Framework Parity Ledger](docs/agent-framework-parity.md) covers
functionality and developer/runtime surfaces for LangGraph, CrewAI, Microsoft
Agent Framework, LlamaIndex, and OpenAI Agents SDK. Adoption and licensing are
intentionally excluded.

| Capability | MAPLE 2.0.0 boundary |
| --- | --- |
| Agent loop, tools, schemas, typed errors | Native local runtime. |
| Workflows, branching, fan-out, retries | Bounded local preview. |
| Guardrails and approval | Fail-closed local preview; hosted identity and policy remain host-owned. |
| Handoffs and agent-as-tool | Bounded local preview with an authenticated remote payload seam. |
| Sessions, memory, checkpoints, history | Local partial/preview surfaces with explicit replay limits. |
| Retrieval, citations, tracing, evaluations | Deterministic local preview surfaces. |
| Hosted runtime, studio, managed stores, multi-language SDKs | Deferred. |
| Sandboxed execution, browser/computer control | Unsupported by the core runtime; handlers remain trusted-host code. |
| Distributed scheduling, federation, exactly-once effects | Deferred; local durability is at-least-once where stated. |

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

## Quick start

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

### Code blocks remain data

~~~python
from maple.autonomy import InMemoryArtifactStore, extract_code_blocks, materialize_code_block

blocks = extract_code_blocks(model_text).unwrap()
store = InMemoryArtifactStore()
for block in blocks:
    artifact = materialize_code_block(store, block).unwrap()
    print(artifact.artifact_id, artifact.size)
~~~

The artifact boundary validates sizes, names, UTF-8 bytes, and SHA-256
identity. It does not run Python, shell, browser, or computer-use code.

## Examples and companion integrations

- [Examples](examples/README.md) - small core and autonomy examples.
- [Legacy hello-world example](example/README.md) - compatibility example.
- [External demo package](demo_package/README.md) - interactive demos; not
  included in the core wheel or sdist.
- [n8n integration](n8n-integration/README.md) - TypeScript nodes and sample
  workflows; not included in the Python distribution.
- [Launch materials](LAUNCH/README.md) - local launch/demo helpers and their
  publication boundary.

## Testing and quality

~~~bash
python -m pytest tests/ -q
python -m black --check maple
python -m isort --check-only maple
python -m flake8 maple/ --max-line-length=88
python -m compileall -q maple
python -m maple.cli doctor --json
~~~

Recorded release evidence includes a complete local suite of 1906 passed and
1 skipped at the final implementation parent, a green hosted matrix on the
release branch, and a clean-archive Gitleaks result of no leaks found. The
full-history scan retained three reviewed synthetic fixture findings without
an allowlist or history rewrite. See the [release QA record](docs/qa/maple-agent-runtime-release-2.0.0.md)
and [ultra-review record](docs/reviews/maple-ultra-review-2.0.0.md).

## Release and website status

MAPLE 2.0.0 is a local, untagged, unpublished candidate. No release tag,
registry upload, cloud call, or website deployment has been performed.

The website is intentionally **in standing**: tracked static assets are held
for a later copy/link/accessibility pass and deployment decision. See
[website/README.md](website/README.md) and the
[external-phase plan](docs/plans/maple-publication-website-cloud-registry.md).

## Documentation map

- [Getting started](docs/getting-started.md)
- [API reference](docs/api-reference.md)
- [Agent-framework parity ledger](docs/agent-framework-parity.md)
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
