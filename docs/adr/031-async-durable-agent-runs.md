# ADR-031: Async durable agent-run checkpoints

**Date:** 2026-08-26  
**Status:** accepted  
**Deciders:** Chief Architect

## Context

ADR-030 added bounded JSON-safe checkpoints to the synchronous ReAct loop. The
async entry point still had no run identity, checkpoint cursor, or restart
resume path. That left the runtime's native async path behind the synchronous
path and behind the parity ledger's durable-run requirement.

The existing `AgentRunStore` contract is synchronous by design and has no new
dependency or cloud requirement. File persistence must not block the event
loop, and an async run waiting for approval must not start later model-requested
tool calls after the pause boundary.

## Decision

Extend `AutonomousAgent.pursue_goal_async` with the same optional keyword-only
`run_id` supported by `pursue_goal`, and add `resume_run_async`. Async
checkpoint loads and saves run through the event loop's executor against the
existing `AgentRunStore` implementations. The checkpoint schema, bounds, CAS
versions, atomic file replacement, JSON-only restoration, and approval result
replacement remain the ADR-030 contract.

When a durable async run is enabled, tool calls in one model step are executed
in order so a pending approval pauses before later tool side effects. Runs
without durable persistence retain the existing bounded concurrent tool fan-out
behavior. A completed tool result is checkpointed before the next model call;
an interrupted model call therefore resumes from the next model step without
repeating that tool.

## Alternatives considered

| Option | Pros | Cons | Why not |
|---|---|---|---|
| Reuse the sync loop in an executor | Minimal code and shared behavior | Loses native async provider/tool behavior and makes cancellation less honest | Async callers need the async provider boundary |
| Add an async store protocol | Native async persistence | Duplicates the store contract and requires new implementations/dependency decisions | Executor-backed local stores preserve the existing additive contract |
| Persist only at final completion | Lowest write volume | A process interruption can lose the completed-tool cursor and repeat side effects | Does not close the recovery gap |
| Persist the whole agent/provider object | More apparent state | Unsafe executable deserialization and provider/tool identity drift | Violates the JSON-safe data boundary |

## Consequences

- Positive: synchronous and asynchronous autonomous goals now share the same
  bounded local run/resume contract and approval pause semantics.
- Positive: file-backed checkpoint I/O does not run directly on the async event
  loop.
- Negative / debt accepted: the durable store is thread-safe only within one
  process; cross-process leases and distributed ownership remain host work.
- Negative / debt accepted: external effects remain at-least-once and require
  handler idempotency when needed; no sandbox or exactly-once claim is made.
- Negative / debt accepted: full trace replay, compaction, durable streaming
  cursors, and arbitrary request/response HITL remain separate follow-on
  capabilities.

