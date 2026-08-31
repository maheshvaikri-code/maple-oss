# ADR-066: Bounded Authenticated Durable Agent-Run Transport

## Status

Accepted — preview capability, local-first.

## Context

MAPLE already persists bounded synchronous and asynchronous autonomous-agent
runs through `AgentRunStore`, including paused approval/input state, result and
error envelopes, optimistic versions, and file-backed fencing leases. The
initial agent HTTP transport invoked a host callback but did not expose that
durable state or provide a way to resume a paused run remotely.

The next parity increment is a small control plane over the existing store and
agent contracts. It must remain useful for a loopback host while making no
hosted-runtime, scheduler, or exactly-once claim.

## Decision

Add an optional authenticated durable agent-run seam:

- `AgentRegistry.register(..., resume_handler=...)` accepts an explicit
  host-owned callback receiving a validated `run_id`.
- `AgentRegistry.resume(agent_id, run_id)` validates and normalizes the
  callback's `AgentRun` envelope using the same rules as new invocation.
- `RunServer(agent_run_store=...)` exposes `GET
  /v1/agents/<agent_id>/runs/<run_id>` for an authoritative checkpoint
  summary.
- `RunServer` exposes `POST
  /v1/agents/<agent_id>/runs/<run_id>/resume` when the registered agent has a
  resume callback.
- `RunClient.inspect_agent_run(...)` and `RunClient.resume_agent_run(...)`
  provide the dependency-free client surface.

The inspection response includes bounded checkpoint identity, description,
status, step/retry counters, pending interaction IDs, session correlation,
token usage, result/error, version, and timestamps. It deliberately omits
persisted messages and reasoning steps. A checkpoint whose `agent_id` does not
match the URL is returned as not found to avoid cross-agent disclosure.

The server requires a bearer token whenever an agent registry or run store is
configured. The token authenticates access to the transport; it does not
create a per-agent principal or authorization scope. Hosts requiring tenancy,
operator roles, or per-agent permissions must enforce those policies around
the server or provide a future scoped contract.

## Alternatives considered

1. **Expose the complete checkpoint, including messages and reasoning trace.**
   Rejected because those fields may contain prompts, tool arguments, user
   responses, or private model context. Remote lifecycle inspection needs
   status and result metadata, not an automatic transcript export.

2. **Add a generic remote scheduler and background job queue.** Rejected for
   this slice because queue ownership, cancellation, retry/idempotency, worker
   leases, backpressure, and delivery semantics would be a separate runtime
   contract. The explicit host callback keeps execution ownership visible.

3. **Infer resume by calling the original invocation handler again.** Rejected
   because re-invocation can repeat model/tool side effects and bypass the
   durable agent's approval/input replay logic. Resume is available only when
   the host explicitly supplies a callback backed by its durable agent state.

## Bounds and failure modes

- Existing path, ID, request, response, JSON, and authentication bounds apply.
- A missing `agent_run_store` returns `503`; a missing or cross-agent run
  returns `404`.
- A missing resume callback returns `501`; callback exceptions are redacted as
  typed server errors.
- Resume callbacks must return the same JSON-safe `AgentRun` envelope as new
  invocation; malformed results fail closed.
- Store version conflicts and waiting/non-resumable states retain typed
  conflict semantics.
- No transport retries, background scheduling, hard cancellation, principal
  scopes, remote event aggregation, payload delivery, or exactly-once external
  effects are provided.
- The server remains loopback-only and does not terminate TLS or issue tokens.

## Consequences

MAPLE can now inspect and explicitly resume a locally persisted agent run over
an authenticated dependency-free HTTP contract. The local durable store and
agent remain authoritative, and wire responses avoid transcript leakage.

Remote orchestration is still intentionally incomplete: a host must provide
authorization, worker lifecycle, cancellation, retry/idempotency, and any
cross-process event/result aggregation it needs.
