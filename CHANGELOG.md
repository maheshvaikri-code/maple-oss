<img width="358" height="358" alt="maple358" src="https://github.com/user-attachments/assets/299615b3-7c74-4344-9aff-5346b8f62c24" />

<img width="358" height="358" alt="mapleagents-358" src="https://github.com/user-attachments/assets/e78a2d4f-837a-4f72-919a-366cbe4c3eb5" />

# MAPLE Changelog

**Creator: Mahesh Vaijainthymala Krishnamoorthy (Mahesh Vaikri)**

## Unreleased

### Additions

- **CI/release preflight**: GitHub Actions now enforces isolated dependency
  consistency, compilation, the network-free doctor, changed-runtime Flake8,
  focused regressions, and built-wheel verification before package release.
- **Live MCP discovery** (`maple.adapters.mcp_adapter`,
  `maple.autonomy.mcp_tools`): added a dependency-free bounded Streamable HTTP
  transport with lazy MCP initialization, JSON/SSE response parsing, live
  paginated `tools/list`, real JSON-RPC `tools/call`, RPC error mapping, and
  strict external descriptor conversion. Live tools require approval by
  default; the historical URL-only discovery call remains offline for
  compatibility.
- **Artifacts and code blocks** (`maple.autonomy.artifacts`): added immutable
  SHA-256-addressed in-memory and file-backed stores with byte quotas, restart
  persistence, hash verification, and a bounded Markdown fence parser that
  returns code as data without executing it. Native sandbox, shell, browser,
  and computer-use execution remain intentionally unimplemented.
- **Provider-agnostic LLM streaming** (`maple.llm.provider`): the shared
  `stream()` contract now yields bounded text chunks, tool-call deltas, and a
  finish event after a successful completion, while preserving typed provider
  errors. Native low-latency provider streams remain explicit overrides.
- **Release metadata hardening**: `pyproject.toml` is now the single source
  for package metadata, the legacy `setup.py` delegates to it, and the source
  manifest includes only files present in the repository. Wheel/sdist builds
  are warning-free and remain Twine-checkable.
- **Native workflow runtime (preview)** (`maple.autonomy.workflow`): validated
  sequential graphs, stable run IDs, JSON-safe node-boundary checkpoints,
  conditional routing, interruption/resume, atomic file persistence, and
  optimistic checkpoint versions. Public API documentation and regression
  tests are included.
- **Typed agent contracts (preview)** (`maple.autonomy.contracts`): bounded
  JSON-Schema validation for tool and model boundaries, structured output
  parsing, and fail-closed input/output guardrails with regression tests.
- **Trusted local execution (preview)** (`maple.autonomy.execution`): bounded
  trusted-handler execution with input/output byte limits, concurrency,
  timeout, cooperative cancellation, approval, and cleanup semantics. The
  public documentation calls out that it is not a hard-kill sandbox.
- **Retrieval/data primitives (preview)** (`maple.autonomy.retrieval`): bounded
  source-bearing documents, deterministic chunking with offsets, and a
  dependency-free lexical retriever with ranked citations and regression tests.
- **Event streaming and redaction (preview)** (`maple.autonomy.events`): bounded
  sequenced event retention, snapshot/wait/subscriber consumers, structured
  payload limits, and recursive credential-key redaction.
- **Evaluation/provider capabilities (preview)** (`maple.autonomy.evaluation`,
  `maple.llm.capabilities`): deterministic output/trajectory evaluation cases,
  redacted bounded reports, declared capability matching, and provider
  initialization fallback.
- **Interop and doctor CLI (preview)** (`maple.autonomy.interop`, `maple.cli`):
  strict versioned JSON adapter envelopes and a network-free machine-readable
  runtime readiness report.

## Version 1.1.3 - Downstream integration improvements (August 2026)

Hardening and extensibility surfaced by integrating MAPLE into a governed
downstream host. All backward-compatible except two intentional behavior
changes (noted below). Full suite: 1002 passed.

### Additions

- **`exponential_backoff(max_delay=...)`** (`maple.error.recovery`): optional
  per-attempt delay ceiling (`min(delay, max_delay)`, applied after jitter).
  Default `None` keeps the prior unbounded behavior. Prevents a large
  `max_attempts` from stalling a caller holding a resource across the backoff.
- **MCP tool governance** (`maple.autonomy.register_mcp_tools`): opt-in host
  hooks for untrusted MCP servers — `policy(tool, server_id)` (fail-closed
  default-deny), `namespace=True` (`mcp.<server_id>.<name>`, prevents
  shadowing), `max_tools` cap, and `sanitize_tool_name()`. No hooks =
  registers all tools as before.
- **`HealthMonitor.snapshot()`** (`maple.monitoring`): immediate on-demand
  health read computed from live counters, without waiting for the first
  sampling interval.
- **Resource model v2** (`maple.resources`): `ResourceLifecycle`
  (`RENEWABLE`/`CONSUMABLE`) + `DEFAULT_LIFECYCLES`; `register_resource(...,
  lifecycle=...)`; `release()` refunds only renewable resources (consumable
  budgets stay spent). `ResourceRequest.custom` for arbitrary named numeric
  dimensions (gpu/disk/money/api_calls/energy). New `LeaseManager`/`Lease` —
  exclusive, TTL-bounded holds with monotonic fencing tokens. Additive exports.

### Fixes / hygiene

- Replaced deprecated `datetime.utcnow()` with the non-deprecated naive-UTC
  equivalent (`maple.core.message`, `maple.security.cryptography_impl`);
  serialization unchanged.

### Behavior changes (intentional)

- `HealthMonitor.get_health_summary()` on a fresh monitor now returns a live
  summary instead of `{"status": "no_data"}`.
- Removed library `logging.basicConfig` from 7 modules — a library must not
  configure the root logger. MAPLE's own INFO logs no longer print unless the
  host configures logging.

---

## Version 1.1.2 - Doctrine wishlist + broker/task fixes (July 2026)

### Fixes

- **Broker double-delivery**: `MessageBroker.send()` enqueued every direct
  message into *both* the basic per-agent queue and the priority
  `MessageQueue`, and the delivery loop drains both — so each message was
  delivered (and each handler fired) twice. `send()` now enqueues into exactly
  one queue (priority queue, with the basic queue as fallback when it is
  unavailable/full). Added a delivered-exactly-once regression test.
- **`TaskQueue` unresponsive shutdown**: the cleanup thread slept with
  `time.sleep(300)`, so `stop()` blocked on its `join(timeout=5.0)` for the
  full 5 s every time — making test teardowns pile up until the suite looked
  hung. The loop now waits on a `threading.Event` that `stop()` sets, so
  shutdown returns promptly.
- **Handler-key case trap** (`Agent.register_handler`): handler keys are now
  normalized to upper-case, matching `Message` (which upper-cases every
  `message_type`). Previously a handler registered as `"work.package"`
  silently never fired for an incoming `WORK.PACKAGE`. Covers the
  `@agent.handler(...)` decorator path too. 5 regression tests. Implements
  enhancement ask #1 from `.Doctrine/integrations/maple.md`.

### Additions

- **Doctrine profile — `WORK.PACKAGE` / `GATE.RESULT` schemas**
  (`maple.adapters.doctrine_adapter`): typed builders + validators for the two
  doctrine protocol message types, beside the a2a/mcp/crewai adapters.
  `build_work_package` / `build_gate_result` return `Result[Message]`;
  `validate_work_package` / `validate_gate_result` check an incoming message;
  `DoctrineAdapter(agent)` dispatches them. Payloads carry artifact hashedrefs
  (via `ArtifactRef`) not prose, so they satisfy the fresh-context verifier
  preset; verdicts are validated against `GATE_VERDICTS`
  (`PASS`/`FAIL`/`BLOCKED`/`WAIVED`). Imported explicitly like the other
  adapters, so `import maple` stays free of the security layer. 34 tests, 100%
  coverage. Implements enhancement ask #4 from `.Doctrine/integrations/maple.md`.
- **Routability / opt-in delivery check** (`MessageBroker.is_routable`,
  `Agent.send(..., require_routable=True)`): `send()` returning `Ok` means
  *enqueued*, not delivered — a message to a nonexistent agent still enqueues.
  `is_routable(agent_id)` reports whether a receiver has a live subscription,
  and `require_routable=True` makes `Agent.send` return `Result.err` with
  `errorType` `UNROUTABLE` instead of a misleading `Ok`. Opt-in — the default
  `send()` behavior is unchanged. 7 regression tests. Implements enhancement
  ask #2 from `.Doctrine/integrations/maple.md`. (Reachability is checked at
  send time; a post-delivery acknowledgement receipt remains future work.)
- **`tokens` resource type** (`ResourceRequest`): LLM token budget is now a
  first-class resource alongside `compute`/`memory`/`bandwidth` — carried
  through `to_dict`/`from_dict` (so it survives negotiation) and handled by
  `ResourceManager` satisfy/allocate/release (numeric, like compute). Lets
  LLM budget negotiation map to loop-engineering caps. 9 regression tests.
  Implements enhancement ask #5 from `.Doctrine/integrations/maple.md`.
- **Fresh-Context Verifier Preset** (`maple.security.separation`): separation
  of duties as a broker-enforced runtime guarantee instead of a convention.
  - `SeparationOfDutiesPolicy` — a per-agent **sender allowlist** (fail-closed
    by default) plus an **artifact-ref-only payload policy** for guarded
    message types (`WORK.PACKAGE`, `GATE.RESULT`), exposed as
    `authorize_send(message) -> Result`.
  - `fresh_context_verifier_preset(orchestrator, builders, verifiers)` — wires
    orchestrator → everyone and each builder/verifier → orchestrator only, so
    a verifier can never route a review back to the author it is judging.
  - `ArtifactRef(path, sha256)` with `of()` / `for_file()` / `to_dict()` and
    the `is_artifact_ref()` validator — content-pinned artifact pointers so a
    builder's prose never travels into a verifier's context.
  - `MessageBroker.send()` **and** `publish()` enforce an attached policy
    (via new optional `SecurityConfig.separation_policy`), raising
    `SecurityError` on violation so `Agent.send()`/`publish()` return
    `Result.err(...)`. A newly-supplied policy is adopted even on the broker
    singleton's re-init, and `set_separation_policy()` is an explicit setter.
  - Hardening (from a fresh-context G4 review): topic fan-out is covered;
    a ref's `path` and dict keys are subject to the prose ceiling; custom
    `guarded_types` are upper-cased to match `Message`; receiver-less sends
    from a listed agent fail closed; deep/cyclic payloads are rejected
    (`PAYLOAD_TOO_DEEP`) instead of overflowing the stack.
  - Enforcement is applied by the in-memory `MessageBroker`; alternate
    transports (`nats_broker`, S2) are out of scope for this change.
  - 52 new tests. Implements enhancement ask #3 from
    `.Doctrine/integrations/maple.md`.

---

## Version 1.1.1 - S2.dev Integration (March 2026)

### Additions

- **S2.dev Durable Streaming**: `S2Broker` and `S2StateBackend` for durable message transport and state persistence via [s2.dev](https://s2.dev)
- **S2 Broker Type**: `BrokerType.S2` registered in `ProductionBrokerManager` with auto-detection from `s2://` broker URLs
- **Adapters Package**: New `maple/adapters/__init__.py` with conditional S2 exports
- **834 tests passing**, 16 new S2 adapter tests

### New Dependencies (optional)

```toml
[project.optional-dependencies]
s2 = ["streamstore>=5.0.0"]
```

---

## Version 1.1.0 - Autonomous Agentic AI (March 2026)

### Major Additions

- **LLM Provider Layer**: Pluggable provider system supporting OpenAI, Anthropic, and compatible APIs (vLLM, Ollama, Together)
- **Autonomous Agent**: ReAct-loop powered `AutonomousAgent` with goal pursuit, multi-step reasoning, reflection, and backtracking
- **Tool Framework**: Extensible `Tool` and `ToolRegistry` with built-in MAPLE tools (send_message, query_agents, read/write state, check resources, establish links)
- **Memory System**: Three-tier memory — `WorkingMemory` (context window), `EpisodicMemory` (task history), `SemanticMemory` (learned facts) — backed by existing `StateStore`
- **Multi-Agent Orchestrator**: `AgentOrchestrator` with supervisor and consensus execution patterns, capability-based team formation
- **MCP Tool Discovery**: Discover and register external MCP server tools as native MAPLE tools via `MCPAdapter`
- **Observability**: `DecisionLogger` and `AgentSnapshot` for full decision tracing and agent state inspection

### Infrastructure Improvements

- **Broker Wiring**: NATS broker auto-detection from `broker_url`, `ProductionBrokerManager` integration
- **Authorization Enforcement**: `AuthorizationManager` auto-initialized in `MessageBroker` when security config present
- **Message Queue & Router**: `MessageQueue` (priority ordering) and `MessageRouter` integrated into broker delivery loop
- **Agent Auto-Registration**: Agents auto-register/deregister in `AgentRegistry` on start/stop
- **Cryptographic Handshake**: Agent handshake uses real `CryptographyManager` (AES-256-GCM) with graceful fallback
- **Circuit Breaker Consolidation**: `TaskScheduler` and `FailureDetector` now use shared `error.circuit_breaker.CircuitBreaker`
- **Agent Metrics**: Built-in counters for messages sent/received/failed, handler errors, processing time
- **S2.dev Integration**: `S2Broker` and `S2StateBackend` for durable streaming via [s2.dev](https://s2.dev), auto-detected from `s2://` broker URLs

### Testing & Quality

- **818 tests passing**, 0 failures
- **80% code coverage** across all modules
- New test suites: LLM providers, autonomous agent, tools, memory, orchestrator, observability, performance optimizer, scheduler, result collector, security init

### New Dependencies (optional)

```toml
[project.optional-dependencies]
llm = ["openai>=1.0.0", "anthropic>=0.20.0"]
s2 = ["streamstore>=5.0.0"]
```

---

## Version 1.0.0 - Initial Release (December 2024)

### Major Changes
- **Protocol**: MAPLE (Multi Agent Protocol Language Engine) Multi Agent Communication Protocol
- **Attribution**: Added comprehensive attribution to Mahesh Vaikri throughout codebase
- **Enhanced Comparisons**: Updated all documentation to compare with major protocols:
  - Google A2A (Agent-to-Agent)
  - FIPA ACL (Foundation for Intelligent Physical Agents - Agent Communication Language)
  - AGENTCY
  - Model Context Protocol (MCP)

### Core Features
- **Rich Type System**: Comprehensive type validation with primitive, collection, and special types
- **Result<T,E> Pattern**: Advanced error handling with explicit success/error types
- **Resource Management**: Built-in resource specification, allocation, and negotiation
- **Link Identification Mechanism**: Secure communication channel establishment
- **Distributed State Management**: Consistency models for large-scale agent systems
- **Message Structure**: Standardized header, payload, and metadata format
- **Communication Patterns**: Request-response, publish-subscribe, streaming, and broadcast

### Security Features
- **Authentication**: JWT-based agent authentication
- **Authorization**: Role-based access control
- **Encryption**: End-to-end message encryption
- **Link Security**: Link Identification Mechanism for secure channels

### Documentation Updates
- **Comprehensive API Documentation**: Complete reference for all MAPLE components
- **Protocol Comparison**: Detailed comparison with competing protocols
- **Usage Examples**: Practical examples for common use cases
- **Best Practices**: Guidelines for effective MAPLE implementation

### Performance Characteristics
- **Scalability**: Support for 10,000+ agents
- **Latency**: 5-15ms message delivery
- **Throughput**: 10,000+ messages per second
- **Reliability**: 99.99% uptime with fault tolerance

### Use Cases
- **Manufacturing Systems**: Industrial automation and robotics coordination
- **Financial Trading**: High-frequency trading agent coordination
- **Smart Cities**: IoT and infrastructure management
- **Autonomous Vehicles**: Vehicle-to-vehicle communication
- **Healthcare**: Medical device and information system coordination

### Technical Improvements
- **Memory Optimization**: Efficient message serialization and processing
- **Network Efficiency**: Optimized protocol overhead
- **Error Recovery**: Circuit breaker pattern and retry mechanisms
- **Resource Optimization**: Dynamic allocation based on agent requirements

### Attribution
All files now include proper attribution:
```
# Creator: Mahesh Vaijainthymala Krishnamoorthy (Mahesh Vaikri)
```

### Repository Structure
```
maple-oss/
├── maple/                 # Core MAPLE implementation
│   ├── core/             # Type system, messages, result handling
│   ├── agent/            # Agent implementation and configuration
│   ├── broker/           # Message routing and delivery
│   ├── security/         # Authentication, authorization, encryption
│   ├── resources/        # Resource management and negotiation
│   ├── communication/    # Communication patterns
│   ├── error/            # Error handling and recovery
│   └── state/            # Distributed state management
├── docs/                 # Comprehensive documentation
├── html_documentation/   # Interactive web documentation
├── sample/               # Usage examples and demos
└── tests/                # Test suite
```

### Breaking Changes
- Package name changed from `mapl` to `maple-oss`
- Import statements updated: `from maple import ...`
- Protocol name changed throughout documentation

### Future Roadmap
- **Formal Verification**: Mathematical verification of protocol correctness
- **Adaptive Protocols**: Self-optimizing communication patterns
- **Cross-Organization**: Multi-tenant agent coordination
- **Quantum Integration**: Quantum-safe cryptography support

**Creator: Mahesh Vaijainthymala Krishnamoorthy (Mahesh Vaikri)**
