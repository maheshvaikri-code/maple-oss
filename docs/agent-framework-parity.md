# MAPLE Agent-Framework Parity Ledger

**Observed:** 2026-08-25
**Scope:** functionality and developer/runtime surfaces only; adoption and
licensing are intentionally excluded.
**Comparison set:** LangGraph, CrewAI, Microsoft Agent Framework (the current
AutoGen successor), LlamaIndex, and OpenAI Agents SDK.

This is a capability ledger, not a market ranking or benchmark. A competitor
column records a representative surface documented by that project's official
documentation. It does not claim that the listed project is the only project
with that capability, nor that an adapter makes MAPLE equivalent to it.

## Status vocabulary

| Status | Meaning |
|---|---|
| **Native** | Implemented in MAPLE's public runtime and covered by repository tests. |
| **Preview** | Implemented, bounded, or opt-in, with an explicitly narrower contract. |
| **Partial** | A useful local subset exists, but an important runtime counterpart is absent. |
| **Adapter** | Interoperability exists; it is not a native MAPLE capability claim. |
| **Deferred** | Deliberately out of the current release scope. |
| **Unsupported** | The public boundary fails closed or does not exist. |

## Capability matrix

| Capability | MAPLE status and evidence | What the comparison set makes visible | Release action |
|---|---|---|---|
| Agent loop, tool calling, and tool schemas | **Native** — `AutonomousAgent`, `Tool`, `ToolRegistry`, ReAct reasoning, bounded arguments, approval-aware execution | All five expose an agent/tool loop as a primary developer surface | Keep stable; add more provider-contract fixtures only when needed |
| Typed input/output and structured generation | **Preview** — typed tool models, `output_model`, bounded JSON/schema parsing, typed guardrails | LlamaIndex, Microsoft Agent Framework, and OpenAI Agents SDK document structured or typed output patterns; the others commonly pair typed state/tools with model schemas | Promote only after broader provider compatibility and failure fixtures |
| Guardrails and policy enforcement | **Preview** — input/output guardrails and fail-closed approval | OpenAI Agents SDK has first-class input/output/tool guardrails; Microsoft Agent Framework documents middleware/security and approval surfaces | Add a unified policy lifecycle and trace linkage |
| Human-in-the-loop approval | **Partial** — durable tool approvals and file-backed human-input records support bounded decisions with per-record cross-process fencing, and the built-in `request_human_input` tool supports schema-validated response/rejection with sync/async durable resume; local notifier and fail-closed actor-authorizer hooks plus same-record bounded follow-up rounds with persisted history are available; `WorkflowPause` supports local pause/resume | LangGraph interrupts, Microsoft request/response ports, LlamaIndex HITL, CrewAI HITL, and OpenAI approval/guardrail patterns cover broader interactive control | P0: add remote authentication/transport and hosted interaction delivery; preserve the local bounded-round and one-shot compatibility boundaries |
| Handoffs and agent-as-tool | **Preview** — `create_handoff_tool` is one bounded, approval-by-default local delegation call with allowlisted JSON context, async target execution when explicitly declared, and optional in-memory/file durable identity with `pending → accepted → completed/failed` ownership transfer | OpenAI Agents SDK and Microsoft Agent Framework distinguish handoff ownership from manager/agent-as-tool; LlamaIndex documents agent workflows and agents-as-tools | P0: remote routing/authentication, scheduling, and exactly-once side-effect policy remain separate |
| Workflow graph, branching, and parallelism | **Preview** — typed nodes, conditional routing, bounded fan-out/fan-in, deterministic joins, and persisted per-node retry/backoff for ordinary node handlers | LangGraph, Microsoft Agent Framework, and LlamaIndex document graph/event workflow composition; CrewAI documents event-driven flows and branching/loops | Add composable sub-workflows and durable retry state for parallel branches |
| Durable checkpoints and recovery | **Partial** — JSON-safe memory/file checkpoints, bounded history, normalized-output journal, local run server, sync/async ReAct run resume, per-run file-backed fencing, and approval/input record ownership | LangGraph persistence/time-travel, Microsoft checkpoints/resume, LlamaIndex durable workflows, and CrewAI persisted flows establish a larger durability surface | P0: restore broader pending requests and document side-effect policy; add hosted/distributed coordination only with an explicit contract |
| Conversation sessions and memory | **Partial** — bounded memory/file session stores plus working, episodic, and semantic memory | CrewAI, Microsoft Agent Framework, LlamaIndex, and OpenAI Agents SDK document session or memory primitives; richer managed context and compaction are common follow-ons | Add trace/tool-result replay and bounded compaction; keep encryption/leases host-owned until specified |
| Streaming | **Preview** — provider-native OpenAI/Anthropic streams plus bounded sync/async agent lifecycle events with opt-in metadata-only `model.chunk` events, response reconstruction, usage trailers, request correlation IDs, serializable cursors, explicit retention-gap errors, cooperative waiter cancellation, and local publish-latency/failure metrics | LangGraph, CrewAI, Microsoft Agent Framework, LlamaIndex, and OpenAI Agents SDK expose run/event streaming | P1: add remote transport and percentile latency/backpressure views; local chunk aggregation remains deliberately bounded |
| Retrieval, RAG, and citations | **Preview** — deterministic chunking, local lexical/vector retrieval, source references, retrieval/groundedness evaluation | LlamaIndex is the strongest reference surface for data connectors, RAG workflows, structured output, and citations; other frameworks expose retrieval integrations | P1: connector/reranker seams and managed-store adapters; do not call lexical overlap semantic faithfulness |
| MCP and external tool ecosystem | **Native + Adapter** — live MCP discovery/call and protocol adapters | MCP is documented across the comparison set as an integration boundary rather than a complete agent runtime | Keep transport bounded; add auth/tenant policy only with a scoped contract |
| Code blocks and artifacts | **Native data surface** — bounded Markdown code-block extraction and content-addressed artifact stores | Frameworks commonly expose code-generation or code-agent examples; that does not imply safe execution | Keep extraction non-executing; document artifact lifecycle and provenance |
| Code interpreter, browser, computer use, and sandboxing | **Unsupported** — `TrustedLocalExecutor` runs explicitly trusted local handlers only; no in-process sandbox or hosted interpreter is claimed | OpenAI Agents SDK documents sandbox agents; LlamaIndex documents CodeAct examples; the Microsoft/CrewAI/LangGraph ecosystems provide execution integrations | P2: separate security brief for isolation, browser controls, approvals, and cleanup; never enable by documentation alone |
| Tracing and observability | **Preview** — bounded `EventStream`, redaction policy, host-owned exporter seam, decision traces/logger with provider correlation, optional thread-safe local `TraceSpan`/`SpanRecorder` model-step linkage, stable span sampling, local latency/status/failure metrics, snapshots | OpenAI Agents SDK tracing and LlamaIndex/CrewAI observability surfaces are broader, especially for exporters and hosted inspection | P1: add remote/exporter delivery, percentile latency views, and approval-replay correlation; local model spans remain bounded |
| Evaluations | **Preview** — versioned deterministic output/schema/trajectory cases plus retrieval and grounded-answer harnesses with redacted reports; optional host-supplied bounded judge result is provider-neutral | OpenAI testing utilities and framework-specific eval/observability integrations support broader trajectory, model-judge, or trace evaluation | P1: async/provider-owned judge orchestration, calibration, and trace scoring; preserve deterministic baseline |
| Retry, cancellation, and resilience | **Native infrastructure / Partial agent runtime** — retry/circuit-breaker primitives, bounded async fan-out, deadlines, cooperative cancellation, and persisted bounded per-node workflow retry/backoff | LangGraph fault-tolerance/retry, LlamaIndex retry policies, and workflow runtimes make step retry more central | Add durable retry state for parallel branches and agent-model/provider retry classification; retain cooperative cancellation truthfulness |
| Provider breadth and portable model contracts | **Native abstraction / Partial adapters** — OpenAI, Anthropic, and compatible provider contracts with capability routing | The comparison set has wider provider/integration catalogs and often provider-specific middleware | Expand only behind capability tests; no provider count claims without live contract evidence |
| Hosting, visual tooling, and managed runtime | **Deferred** — loopback `RunServer` only; no hosted multi-tenant service, dashboard, or studio | Microsoft hosting, LlamaIndex server/deploy tooling, and ecosystem UIs make this a separate product surface | Defer until local contracts, auth, tenancy, and cloud target are explicitly approved |
| Language SDK breadth | **Deferred** — Python runtime | Microsoft Agent Framework and LlamaIndex document multiple language surfaces; others have additional SDK/community surfaces | P2: define a language-neutral protocol contract before another SDK |
| Infrastructure and protocol security | **Native differentiator** — broker, resource negotiation, leases, circuit breakers, cryptographic link/security layers, discovery/health, and protocol adapters | This is not the primary center of gravity of the five agent runtimes | Keep as MAPLE's distinct strength; do not use it to hide the runtime gaps above |

The local observability contract now includes bounded `agent.tool` child spans
for normal sync and async tool execution under the active model span. Hosted
export, sampling/backpressure metrics, approval-replay correlation, and remote
trace search remain separate boundaries.

Local `EventStream.metrics()` and `SpanRecorder.metrics()` now expose bounded
retention/eviction pressure, subscriber count, open-span count, stable span
sampling, coarse latency, and subscriber/exporter failures without a metrics
backend. Percentile histograms and remote aggregation remain deferred.

## Highest-value gaps before a publish claim

The next implementation work should be ordered by runtime correctness, not by
the number of framework checkmarks:

1. **Durable agent runs and interactive control:** persist the run envelope,
   pending requests, approval state, handoff context, and resumable step
   cursor across processes. Define side-effect/idempotency rules before
   promising exactly-once behavior.
2. **Handoff and workflow composition:** support explicit context filtering,
   composable sub-workflows with per-step retry policy, and separately review
   remote routing/authentication and exactly-once side-effect policy around the
   local durable handoff identity.
3. **Unified streaming and observability:** local provider chunk aggregation
   and metadata-only `model.chunk` lifecycle events now link bounded usage and
   provider correlation into agent runs, and optional local model spans link
   chunks, responses, decisions, and normal tool executions. Add percentile
   latency views and remote transport while retaining local sampling,
   cancellation, and the host-owned exporter seam.
4. **Evaluation depth:** retain deterministic retrieval/grounding metrics and
   add versioned trajectory fixtures plus an optional model-judge contract.
5. **Execution integrations:** treat sandbox/browser/computer use, managed
   vector stores, hosted runtime, visual tooling, and additional languages as
   separate reviewed projects—not implicit parity work.

## Explicit non-claims

MAPLE does not claim parity with a framework merely because an adapter exists.
In particular, the AutoGen adapter is an interoperability surface; the
comparison target is the current Microsoft Agent Framework. Redis state
operations, mutual-TLS, OAuth2, and untrusted code execution remain
fail-closed or unsupported as recorded in the [release brief](briefs/maple-agent-runtime-release.md).

## Official reference documentation

These links were consulted on 2026-08-25 and should be rechecked before a
future parity update:

- [LangGraph overview](https://docs.langchain.com/oss/python/langgraph/overview), [persistence](https://docs.langchain.com/oss/python/langgraph/persistence), [human-in-the-loop](https://docs.langchain.com/oss/python/langchain/human-in-the-loop), and [fault tolerance](https://docs.langchain.com/oss/python/langgraph/fault-tolerance)
- [CrewAI flows](https://docs.crewai.com/en/concepts/flows) and [memory](https://docs.crewai.com/en/concepts/memory)
- [Microsoft Agent Framework overview](https://learn.microsoft.com/en-us/agent-framework/), [workflow concepts](https://learn.microsoft.com/en-us/agent-framework/concepts/workflows/), [HITL](https://learn.microsoft.com/en-us/agent-framework/workflows/human-in-the-loop), and [checkpoints](https://learn.microsoft.com/en-us/agent-framework/workflows/checkpoints)
- [LlamaIndex agent workflows](https://developers.llamaindex.ai/python/llamaagents/workflows/) and [structured output](https://docs.llamaindex.ai/en/latest/understanding/agent/structured_output/)
- [OpenAI Agents SDK agents](https://openai.github.io/openai-agents-python/agents/), [handoffs](https://openai.github.io/openai-agents-python/handoffs/), [sessions](https://openai.github.io/openai-agents-python/sessions/), [tracing](https://openai.github.io/openai-agents-python/tracing/), and [testing](https://openai.github.io/openai-agents-python/testing/)
