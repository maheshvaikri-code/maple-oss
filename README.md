<div align="center"> <img width="354" align="centre" height="174" alt="fulstretch" src="https://github.com/user-attachments/assets/e9eaf167-712f-448c-adf3-d55a0562cff7" /> </div>

# MAPLE - Multi Agent Protocol Language Engine

**Creator: Mahesh Vaijainthymala Krishnamoorthy (Mahesh Vaikri)**

<p>
<a href="https://github.com/maheshvaikri-code/maple-oss"><img src="https://img.shields.io/badge/version-1.1.0-brightgreen" alt="Version"></a>
<a href="https://github.com/maheshvaikri-code/maple-oss"><img src="https://img.shields.io/badge/Python-3.8%20|%203.9%20|%203.10%20|%203.11%20|%203.12%20|%203.13-brightgreen" alt="Python"></a>
<a href="https://github.com/maheshvaikri-code/maple-oss"><img src="https://img.shields.io/badge/Tests-818%20PASSED-brightgreen" alt="Tests"></a>
<a href="https://github.com/maheshvaikri-code/maple-oss"><img src="https://img.shields.io/badge/Coverage-80%25-brightgreen" alt="Coverage"></a>
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

### Autonomous Agentic AI (v1.1.0)

- **ReAct Reasoning Loop** — Agents think, act, and reflect autonomously. Built-in backtracking when approaches fail.
- **Pluggable LLM Providers** — OpenAI, Anthropic Claude, or any compatible API (vLLM, Ollama, Together AI).
- **Tool Framework** — Register custom tools with JSON Schema parameters. Built-in tools for inter-agent communication, state read/write, resource checks, and secure link establishment.
- **Three-Tier Memory** — Working memory (context window), episodic memory (task history), semantic memory (learned facts). LLM-assisted summarization when context fills up.
- **Multi-Agent Orchestration** — Form teams by capability, execute via supervisor delegation or consensus voting.
- **MCP Tool Discovery** — Discover and use tools from any MCP server as native MAPLE tools.
- **Observability** — Full decision traces, agent snapshots, token usage tracking.

### Production Infrastructure

- **Result\<T,E\> Error Handling** — Rust-inspired type-safe results. No silent failures, no uncaught exceptions. Chain with `.map()`, `.and_then()`, `.map_err()`.
- **Resource-Aware Messaging** — Agents declare CPU, memory, and bandwidth requirements as first-class protocol features.
- **Link Identification Mechanism (LIM)** — Cryptographic channel verification using AES-256-GCM between agents.
- **Distributed State** — Shared state across agents with configurable consistency levels and change listeners.
- **Circuit Breakers & Retry** — Automatic failure detection, exponential backoff, and circuit breaker patterns.
- **Priority Message Queuing** — Messages routed by priority with health-aware routing.
- **Task Management** — Task queue, scheduler (capability matching + load balancing), fault-tolerant execution, result collection with 7 aggregation strategies.
- **Agent Discovery** — Auto-registration, capability matching, health monitoring, failure detection.
- **9 Protocol Adapters** — Interop with A2A, MCP, FIPA ACL, AutoGen, CrewAI, LangGraph, OpenAI SDK, IBM ACP, S2.

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

| Feature | MAPLE | LangGraph | CrewAI | AutoGen | Google A2A | MCP |
| ------- | ----- | --------- | ------ | ------- | ---------- | --- |
| Autonomous agents (ReAct) | Built-in | Built-in | Built-in | Built-in | No | No |
| Resource specification in protocol | Built-in | No | No | No | Via payload | No |
| Result\<T,E\> error handling | Built-in | No | No | No | No | No |
| Circuit breakers & fault tolerance | Built-in | No | No | No | No | No |
| Cryptographic link security (LIM) | Built-in | No | No | No | OAuth | Platform |
| Distributed state management | Built-in | Checkpointer | No | No | No | No |
| Agent discovery & health monitoring | Built-in | No | No | No | Agent Cards | No |
| Priority message queuing | Built-in | No | No | No | No | No |
| Task scheduling & load balancing | Built-in | No | No | No | No | No |
| Multi-agent orchestration | Built-in | Built-in | Built-in | Built-in | No | No |
| Tool framework | Built-in | Built-in | Built-in | Built-in | No | Built-in |
| Memory system | Built-in | Partial | Partial | No | No | No |
| MCP tool discovery | Built-in | No | No | No | No | Native |
| Protocol adapters | 9 adapters | No | No | No | No | No |

**Where MAPLE excels:** Production infrastructure + autonomous reasoning in one framework. If your agents need resource awareness, security, fault tolerance, AND autonomous decision-making — MAPLE provides all of these as first-class features.

**Where others are stronger:** LangGraph has deeper graph-based workflow primitives. CrewAI has simpler role-based setup. A2A and MCP have broader language support and larger ecosystems. AutoGen has mature human-in-the-loop patterns.

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

Current status: **818 tests passing**, **80% code coverage**.

---

## Examples

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
│   └── adapters/            9 protocol adapters
├── tests/                   818 tests across all modules
├── docs/                    Comprehensive documentation
├── examples/                Autonomous agent and team examples
├── demo_package/            Interactive demos and web dashboard
├── n8n-integration/         Visual workflow nodes for n8n
├── pyproject.toml           Package configuration
├── setup.py                 Legacy setup script
└── VERSION                  Current version (1.1.0)
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

Licensed under the **GNU Affero General Public License v3.0** (AGPL-3.0).

- Free to use, study, modify, and share
- Derivative works must remain open source
- Network use requires source disclosure

See [LICENSE](LICENSE) for complete terms.

---

**MAPLE - Multi Agent Protocol Language Engine**
**Creator: Mahesh Vaijainthymala Krishnamoorthy (Mahesh Vaikri)**

- Email: [mahesh@mapleagent.org](mailto:mahesh@mapleagent.org)
- GitHub: [github.com/maheshvaikri-code/maple-oss](https://github.com/maheshvaikri-code/maple-oss)
- Issues: [Report bugs or request features](https://github.com/maheshvaikri-code/maple-oss/issues)
- Website: [mapleagent.org](https://mapleagent.org)
