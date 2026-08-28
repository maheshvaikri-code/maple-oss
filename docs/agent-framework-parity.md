# MAPLE Agent-Framework Parity Ledger

**Observed:** 2026-08-27
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

The local authenticated control plane now supports host-configured
`Principal` scopes for known health, workflow, agent, approval, interaction,
handoff, and event routes. Remaining principal-scope gaps in the rows below
refer to delegated child-run identity, remote delivery, and policy evaluation,
not the local route gate itself.

Provider requirements can also explicitly require a declared native async
completion capability. This prevents an async caller that needs a non-blocking
provider from selecting a descriptor that only inherits the synchronous
compatibility fallback.

Memory summary archiving now preserves the working context until episodic
persistence succeeds. This closes a local no-loss boundary; cross-store
transactions, automatic/token-aware summarization, managed memory, and hosted
context services remain separate.

Episodic memory now also bounds task IDs, serialized event bytes, and retained
events per task, with reject-before-write errors and newest-window retention.
The quota is local to each store instance; distributed memory, semantic
indexing, and automatic summarization remain separate.

Episodic keyword search now bounds query size and result count and propagates
store or malformed-history errors. It remains local keyword matching rather
than semantic retrieval or a distributed index.

The local `TaskQueue` now validates a bounded `1..100,000` capacity shared by
all priorities, discards stale cancelled or completed tuples before assignment,
and preserves failed-task state when a requeue is rejected for capacity. This
is an in-process admission boundary; durable queues, distributed scheduling,
remote workers, and hosted scheduler ownership remain separate.

Local scheduler assignment now uses an atomic queue-side claim, rejects
duplicate task ownership, and returns scheduler assignment failures through
physical bounded retry admission. This closes a local task-loss boundary; it
does not provide durable scheduling, distributed leases, or hosted worker
coordination.

Task completion is also an ownership-checked queue transition: only the
assigned agent can complete an `ASSIGNED` or `RUNNING` task, and scheduler load
is released after the queue records `COMPLETED`. This is a local lifecycle
invariant, not a distributed lease, durable queue, or exactly-once side-effect
guarantee.

Local rebalancing uses a separate atomic ownership transfer for `ASSIGNED`
tasks. It cannot move `RUNNING` tasks or bypass the current owner check, so
load maps and queue ownership remain aligned within one process. Worker
heartbeats, crash reconciliation, distributed leases, and hosted scheduling
remain separate.

Scheduler capacity is reserved under the local scheduler lock before the queue
claim and rolled back if that claim fails. This closes concurrent local
over-admission for `max_concurrent_per_agent`; it is not a distributed quota,
worker heartbeat, or hosted admission service.

Durable run stores now reject contradictory pending-request state before
mutation: paused checkpoints identify exactly one approval or human-input
record, and non-paused checkpoints identify none. This protects the local
resume cursor from ambiguous recovery; it does not add distributed recovery,
remote request delivery, or exactly-once side effects.

Sync and async durable resume also bind a pending approval or human-input
record to its persisted tool-call placeholder before any handler execution or
input consumption. A missing or mismatched placeholder fails with
`RUN_PENDING_TOOL_MISSING` and preserves the request state. This is local
correlation protection, not a globally unique request identity or distributed
side-effect protocol.

Built-in agent-run stores now retain bounded version-ordered checkpoint history
for local inspection. In-memory history lasts for the process, while the file
store atomically replaces a validated `.history` JSON sidecar so snapshots
survive restart. The surface returns detached data only; it does not restore a
checkpoint, replay handlers, or claim a cross-file transaction.

Failure acknowledgement follows the same local ownership rule: only the
recorded agent can transition an `ASSIGNED` or `RUNNING` task to `FAILED`, and
the scheduler releases capacity only after the queue accepts the error. Retry
is explicit through bounded `requeue_task()` admission; there is no automatic
distributed retry or exactly-once side-effect claim.

`SchedulingPolicy` also rejects invalid strategy names and unbounded worker
configuration before a scheduler starts. The local limits are explicit and
finite; policy distribution, durable schedule state, distributed leases, and
hosted scheduler administration remain separate.

Working-memory admission is also bounded in the local runtime: budgets accept
1..1,000,000 estimated tokens, storage retains at most 4,096 entries, keys are
limited to 256 UTF-8 bytes, and invalid or non-fitting entries fail before
mutation. This improves the local memory boundary while automatic/token-aware
summarization, managed context windows, and hosted memory remain separate.

| Capability | MAPLE status and evidence | What the comparison set makes visible | Release action |
|---|---|---|---|
| Agent loop, tool calling, and tool schemas | **Native** — `AutonomousAgent`, `Tool`, `ToolRegistry`, ReAct reasoning, bounded arguments, approval-aware execution | All five expose an agent/tool loop as a primary developer surface | Keep stable; add more provider-contract fixtures only when needed |
| Typed input/output and structured generation | **Preview** — typed tool models, `output_model`, bounded JSON/schema parsing, typed guardrails | LlamaIndex, Microsoft Agent Framework, and OpenAI Agents SDK document structured or typed output patterns; the others commonly pair typed state/tools with model schemas | Promote only after broader provider compatibility and failure fixtures |
| Multimodal image input | **Preview** — bounded ordered text/image `ChatMessage` parts, validated HTTPS or base64 image sources, OpenAI-compatible formatting, Anthropic base64 formatting, JSON-safe session/run persistence, and explicit `image_input` capability routing | OpenAI Agents SDK, Microsoft Agent Framework, LlamaIndex, and CrewAI document multimodal or vision-oriented model inputs; provider support remains model-specific | Add provider/model fixtures and host-owned media policy before claiming audio/video, fetching, transcoding, or generated media |
| Guardrails and policy enforcement | **Preview** — input/output guardrails and fail-closed approval with bounded `GuardrailEvent` lifecycle metadata and local run/span-linked `guardrail.*` events | OpenAI Agents SDK has first-class input/output/tool guardrails; Microsoft Agent Framework documents middleware/security and approval surfaces | Add remote policy engines, principal scopes, and mandatory hosted audit only through separate host-owned contracts |
| Human-in-the-loop approval | **Partial** — durable tool approvals and file-backed human-input records support bounded decisions with per-record cross-process fencing, and the built-in `request_human_input` tool supports schema-validated response/rejection with sync/async durable resume; local notifier and fail-closed actor-authorizer hooks plus same-record bounded follow-up rounds with persisted history are available; authenticated `RunServer`/`RunClient` approval control routes now list, inspect, and decide without remote consume/execute; `WorkflowPause` supports local pause/resume | LangGraph interrupts, Microsoft request/response ports, LlamaIndex HITL, CrewAI HITL, and OpenAI approval/guardrail patterns cover broader interactive control | P0: add hosted identity, notification/delivery, and principal scopes; preserve the local bounded-round and one-shot compatibility boundaries |
| Handoffs and agent-as-tool | **Preview** — `create_handoff_tool` provides one bounded, approval-by-default ownership transfer, while `create_agent_tool` provides manager-style nested invocation that retains caller ownership; both use allowlisted JSON context and explicit sync/async target contracts, and both return bounded target results | OpenAI Agents SDK and Microsoft Agent Framework distinguish handoff ownership from manager/agent-as-tool; LlamaIndex documents agent workflows and agents-as-tools | P0: remote routing/authentication, scheduling, child-run coordination, and exactly-once side-effect policy remain separate |
| Workflow graph, branching, and parallelism | **Preview** — typed nodes, conditional routing, bounded fan-out/fan-in, deterministic joins, persisted bounded retry/backoff for ordinary nodes and parallel branches, and composable child workflows with explicit state maps and durable pause/recovery | LangGraph, Microsoft Agent Framework, and LlamaIndex document graph/event workflow composition; CrewAI documents event-driven flows and branching/loops | Keep remote routing, distributed scheduling, and exactly-once effects separate |
| Durable checkpoints and recovery | **Partial** — JSON-safe memory/file checkpoints, bounded version history, normalized-output journal, opt-in successful tool-result replay, built-in approval stores with bounded terminal-outcome replay, local run server, sync/async ReAct run resume, per-run file-backed fencing, approval/input record ownership, and authenticated remote inspection/resume/cooperative cancellation through explicit host callbacks | LangGraph persistence/time-travel, Microsoft checkpoints/resume, LlamaIndex durable workflows, and CrewAI persisted flows establish a larger durability surface | P0: broaden pending-request replay and define side-effect policy around remote coordination; history is inspection-only and does not provide restore/replay; hard cancellation, scheduling, principal scopes, and hosted/distributed coordination require explicit contracts |
| Conversation sessions and memory | **Partial** — bounded memory/file session stores plus working, episodic, and semantic memory; durable tool-result replay and host-supplied summary compaction with a retained recent tail are available through local stores | CrewAI, Microsoft Agent Framework, LlamaIndex, and OpenAI Agents SDK document session or memory primitives; richer managed context and automatic compaction are common follow-ons | Add broader trace replay; keep encryption/leases and automatic/token-aware summarization host-owned until specified |
| Streaming | **Preview** — provider-native OpenAI/Anthropic streams plus bounded sync/async agent lifecycle events with opt-in metadata-only `model.chunk` events, response reconstruction, usage trailers, request correlation IDs, serializable cursors, explicit retention-gap errors, cooperative waiter cancellation, local publish-latency/failure metrics with bounded p50/p95/p99 views, authenticated single-event/batch ingestion plus cursor reads from a host-owned stream, an explicit `EventForwarder` with fenced durable consumer cursors for bounded at-least-once remote aggregation, an opt-in `EventForwarderScheduler` with one worker, bounded batches per tick, cooperative shutdown, and local metrics, and optional receiver-side `InMemoryEventDeduplicationStore` suppression keyed by stable source ID and source sequence | LangGraph, CrewAI, Microsoft Agent Framework, LlamaIndex, and OpenAI Agents SDK expose run/event streaming | P1: add hosted aggregation, durable distributed deduplication, and hosted scheduling; local scheduling/backpressure, chunk aggregation, remote cursor reads, explicit forwarding, and bounded in-memory duplicate suppression remain deliberately scoped |
| Retrieval, RAG, and citations | **Preview** — bounded host-owned cursor connectors and ingestion, deterministic chunking, local lexical/vector retrieval, source references, provider-neutral bounded host-supplied reranking, retrieval/groundedness evaluation, optional `InMemoryDocumentCursorCheckpointStore`/`FileDocumentCursorCheckpointStore` restart cursors with atomic revision fencing, and optional `InMemoryDocumentConnectorRateLimiter` admission control | LlamaIndex is the strongest reference surface for data connectors, RAG workflows, structured output, and citations; other frameworks expose retrieval integrations | P1: managed-store adapters; rate limiting is local, fail-fast, and host-owned, while checkpointed sink progress is explicitly at-least-once and lexical overlap/provider scores are not semantic faithfulness |
| MCP and external tool ecosystem | **Native + Adapter** — live MCP discovery/call and protocol adapters | MCP is documented across the comparison set as an integration boundary rather than a complete agent runtime | Keep transport bounded; add auth/tenant policy only with a scoped contract |
| Code blocks and artifacts | **Native data surface** — bounded Markdown code-block extraction and content-addressed artifact stores | Frameworks commonly expose code-generation or code-agent examples; that does not imply safe execution | Keep extraction non-executing; document artifact lifecycle and provenance |
| Code interpreter, browser, computer use, and sandboxing | **Unsupported** — `TrustedLocalExecutor` runs explicitly trusted local handlers only; no in-process sandbox or hosted interpreter is claimed | OpenAI Agents SDK documents sandbox agents; LlamaIndex documents CodeAct examples; the Microsoft/CrewAI/LangGraph ecosystems provide execution integrations | P2: separate security brief for isolation, browser controls, approvals, and cleanup; never enable by documentation alone |
| Tracing and observability | **Preview** — bounded `EventStream`, redaction policy, dependency-free `HttpEventExporter` seam, authenticated single-event/batch ingestion and cursor inspection from a host-owned stream, explicit bounded `EventForwarder` remote aggregation with durable cursors, opt-in `EventForwarderScheduler` polling with bounded local backpressure and lifecycle metrics, optional receiver-side source-sequence deduplication, decision traces/logger with provider correlation, optional thread-safe local `TraceSpan`/`SpanRecorder` model-step linkage, stable span sampling, local latency/status/failure metrics with bounded p50/p95/p99 views, snapshots, and bounded durable approval `trace_id`/`span_id` joins in approval records and lifecycle events | OpenAI Agents SDK tracing and LlamaIndex/CrewAI observability surfaces are broader, especially for exporters and hosted inspection | P1: add hosted aggregation, durable distributed deduplication, and hosted scheduling; local model spans, percentile samples, explicit forwarding, scheduler metrics, bounded in-memory suppression, and approval correlation remain bounded |
| Evaluations | **Preview** — versioned deterministic output/schema cases, structured bounded tool trajectories, retrieval and grounded-answer harnesses with redacted reports, and sequential `EvaluationHarness.run_async(...)` support for sync/awaitable runners plus host-owned judges | OpenAI testing utilities and framework-specific eval/observability integrations support broader trajectory, model-judge, or trace evaluation | P1: provider-owned judge orchestration, calibration, and trace scoring; async callback support is local, bounded, and does not select providers or claim semantic faithfulness |
| Retry, cancellation, and resilience | **Native infrastructure / Partial agent runtime** — retry/circuit-breaker primitives, bounded async fan-out, deadlines, cooperative cancellation, persisted bounded workflow retry/backoff for ordinary nodes and parallel branches, opt-in sync/async model retries for exact classified provider failures, and authenticated host-owned remote cancellation callbacks | LangGraph fault-tolerance/retry, LlamaIndex retry policies, and workflow runtimes make step retry more central | Add provider-specific contract fixtures and remote/circuit-integrated coordination; retain cooperative cancellation truthfulness and do not claim force termination |
| Provider breadth and portable model contracts | **Native abstraction / Partial adapters** — OpenAI, Anthropic, and compatible provider contracts with tool/streaming/structured-output/context/image-input capability routing | The comparison set has wider provider/integration catalogs and often provider-specific middleware | Expand only behind capability tests; no provider count claims without live contract evidence |
| Hosting, visual tooling, and managed runtime | **Deferred** — loopback `RunServer` plus dependency-free `RunClient` transport contract; no hosted multi-tenant service, dashboard, or studio | Microsoft hosting, LlamaIndex server/deploy tooling, and ecosystem UIs make this a separate product surface | Defer hosted service until local contracts, TLS, auth, tenancy, and cloud target are explicitly approved |
| Language SDK breadth | **Deferred** — Python runtime | Microsoft Agent Framework and LlamaIndex document multiple language surfaces; others have additional SDK/community surfaces | P2: define a language-neutral protocol contract before another SDK |
| Infrastructure and protocol security | **Native differentiator** — broker, resource negotiation, leases, circuit breakers, cryptographic link/security layers, discovery/health, and protocol adapters | This is not the primary center of gravity of the five agent runtimes | Keep as MAPLE's distinct strength; do not use it to hide the runtime gaps above |

The workflow transport contract now includes a dependency-free `RunClient`
with bounded JSON responses and optional bearer authentication on
`RunServer`. Loopback binding remains the default; TLS, token issuance,
tenancy, and remote scheduling remain host-owned.

The same authenticated loopback transport now has an optional
`AgentRegistry`/`RunClient.run_agent(...)` seam for one-way invocation of
host-owned synchronous handlers. Agent IDs, task/context/session/run inputs,
JSON-safe results, and handler exceptions are bounded and typed. A configured
`AgentRunStore` exposes redacted checkpoint inspection, while an explicit
`resume_handler` and `cancel_handler` callbacks enable remote resume and
cooperative cancellation through the same normalized result envelope.
Messages and reasoning steps stay off-wire. Token propagation, checkpoint
mutation, hard termination, scheduling, retries, principal scopes, remote
event aggregation, and exactly-once effects remain host-owned or deferred.

The authenticated agent-run control plane now exposes
`POST /v1/agents/<agent_id>/runs/<run_id>/cancel` when a host registers a
`cancel_handler`. The callback must return a `cancelled` `AgentRun`; this is a
request boundary, not a force-kill or exactly-once side-effect guarantee.

Remote handoff identity now has an optional authenticated `RunServer`/
`RunClient` control plane over the existing digest-only `HandoffStore`.
Create, inspect, list, accept, complete, and fail transitions retain the
store's ownership and fencing semantics; raw task/context delivery, per-agent
principal scopes, notifications, retries, and exactly-once effects remain
separate.

The same authenticated transport can now receive one bounded event at a time or
a 1–100 item batch through `POST /v1/events` and `POST /v1/events/batch` into a
host-owned `EventStream`. The receiver assigns local sequence/timestamp values
and re-applies event redaction and size limits. Batch responses preserve input
indexes and make partial item failures explicit. An optional
`FileEventJournal` atomically replays the bounded already-redacted local window
across process restarts, with sequence continuity and fail-closed load/append
validation. `EventForwarder` combines that source window with an authenticated
batch sender and a fenced durable cursor; only the contiguous acknowledged
prefix advances, and delivery remains explicitly at-least-once. Hosted fleet
aggregation, automatic scheduling, and remote trace search remain separate.
An authenticated receiver may opt into `InMemoryEventDeduplicationStore` for
bounded suppression of repeated forwarded source sequences. The sender carries
a stable `source_id` plus each source event's sequence; matching completed
claims replay the redacted destination event, while conflicting content and
concurrent pending claims fail closed. Capacity, TTL, process restart, and
multi-store deployments can still permit duplicates, so durable distributed
deduplication and exactly-once effects remain separate.

The bounded session contract now also includes optional host-supplied summary
compaction with a retained recent tail and optimistic version checks on the
built-in memory/file stores. Automatic or token-aware LLM summarization,
broader trace replay, and cross-process session leases remain separate.

The local observability contract now includes bounded `agent.tool` child spans
for normal sync and async tool execution under the active model span. Durable
approval requests retain optional `trace_id`/`span_id` values from the creating
model span, pending errors carry that join, and `tool.completed` events include
the active model span plus a pending approval ID when applicable. Hosted
export, sampling/backpressure metrics, and remote trace search remain separate
boundaries.

Local `EventStream.metrics()` and `SpanRecorder.metrics()` now expose bounded
retention/eviction pressure, subscriber count, open-span count, stable span
sampling, coarse latency, and subscriber/exporter failures without a metrics
backend. Percentile histograms and remote aggregation remain deferred.

`HttpEventExporter` is an optional synchronous, dependency-free best-effort
HTTP sink for already-redacted events. It bounds event/response bytes, applies
finite timeouts, requires HTTPS for non-loopback endpoints, and performs no
retry or persistence. A host can configure `RunServer(event_stream=...)` and
use `RunClient.publish_event(...)` or `publish_events(...)`, or point the
exporter at `POST /v1/events`;
the receiver assigns local sequence/timestamp values and re-applies the stream
redaction and size boundary. Local bounded replay is available through
`FileEventJournal`; remote durable replay, fleet aggregation, and hosted trace
search remain deferred.

The bounded human-input transport now also exposes optional authenticated
loopback `RunServer`/`RunClient` routes for listing, inspection, response,
rejection, bounded continuation, and one-time consumption. The configured
`HumanInputStore` remains authoritative for schema validation, actor
authorization, leases, notifications, and durable state; hosted identity,
TLS, automatic scheduling, and exactly-once effects remain separate.

Built-in approval stores now retain one bounded terminal tool outcome after a
consumed approval executes. Direct calls and durable sync/async run resume can
replay a recorded outcome without invoking the handler again; a consumed
request without an outcome fails closed as effect-uncertain. This is an
at-least-once crash-window guard, not an exactly-once external side-effect
protocol.

The authenticated loopback transport now also exposes bounded approval control
through `GET /v1/approvals/pending/<limit>`, `GET /v1/approvals/<id>`, and
`POST /v1/approvals/<id>/decide`. The configured approval store remains
authoritative; the transport records decisions but never consumes or executes a
tool. Hosted identity, notifications, scheduling, tenancy, and exactly-once
effects remain separate.

## Highest-value gaps before a publish claim

The next implementation work should be ordered by runtime correctness, not by
the number of framework checkmarks:

1. **Durable agent runs and interactive control:** persist the run envelope,
   pending requests, approval state, handoff context, and resumable step
   cursor across processes. Successful replay for explicitly opted-in tools
   now covers a saved local crash window; broader pending-request replay and
   side-effect/idempotency rules are still required before promising exactly-once
   behavior.
2. **Handoff and workflow composition:** local context filtering,
   composable sub-workflows, per-step retry policy, and durable local handoff
   identity are now available; separately review remote routing/authentication
   and exactly-once side-effect policy around those local boundaries.
3. **Unified streaming and observability:** local provider chunk aggregation and
bounded local scheduling now exist; hosted aggregation, remote deduplication,
hosted scheduling, approval-replay correlation, and remote trace search remain
separate.
   and metadata-only `model.chunk` lifecycle events now link bounded usage and
   provider correlation into agent runs, and optional local model spans link
   chunks, responses, decisions, and normal tool executions. Percentile latency
   views are now local and bounded; `EventForwarder` adds explicit bounded
   remote aggregation with fenced durable cursors while retaining local
   sampling, cancellation, and the host-owned exporter seam. Hosted aggregation,
   provider-owned judge orchestration, calibration, and trace scoring remain
   separate.
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

The built-in OpenAI-compatible and Anthropic adapters also expose native async
completion when their optional SDKs provide async clients. SDKs without that
surface use the explicit synchronous compatibility fallback; this is not a
non-blocking guarantee. Other provider-specific async behavior remains subject
to adapter contract fixtures.

## Official reference documentation

These links were consulted on 2026-08-25 and should be rechecked before a
future parity update:

- [LangGraph overview](https://docs.langchain.com/oss/python/langgraph/overview), [persistence](https://docs.langchain.com/oss/python/langgraph/persistence), [human-in-the-loop](https://docs.langchain.com/oss/python/langchain/human-in-the-loop), and [fault tolerance](https://docs.langchain.com/oss/python/langgraph/fault-tolerance)
- [CrewAI flows](https://docs.crewai.com/en/concepts/flows) and [memory](https://docs.crewai.com/en/concepts/memory)
- [Microsoft Agent Framework overview](https://learn.microsoft.com/en-us/agent-framework/), [workflow concepts](https://learn.microsoft.com/en-us/agent-framework/concepts/workflows/), [HITL](https://learn.microsoft.com/en-us/agent-framework/workflows/human-in-the-loop), and [checkpoints](https://learn.microsoft.com/en-us/agent-framework/workflows/checkpoints)
- [LlamaIndex agent workflows](https://developers.llamaindex.ai/python/llamaagents/workflows/) and [structured output](https://docs.llamaindex.ai/en/latest/understanding/agent/structured_output/)
- [OpenAI Agents SDK agents](https://openai.github.io/openai-agents-python/agents/), [handoffs](https://openai.github.io/openai-agents-python/handoffs/), [sessions](https://openai.github.io/openai-agents-python/sessions/), [tracing](https://openai.github.io/openai-agents-python/tracing/), and [testing](https://openai.github.io/openai-agents-python/testing/)
