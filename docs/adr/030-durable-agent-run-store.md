# ADR-030: Bounded durable agent-run checkpoints

**Date:** 2026-08-25
**Status:** accepted
**Deciders:** Chief Architect

## Context

MAPLE currently persists completed user/assistant turns, durable tool approval
requests, and workflow checkpoints, but an autonomous ReAct run has no durable
message cursor. A process interruption can therefore lose the in-flight model
context and may repeat a completed tool side effect when the host retries the
goal. The parity ledger identifies restart-safe agent runs and interactive
approval resume as the highest-value runtime gap.

The first slice must remain local-first and dependency-free. It needs bounded
JSON-safe state, atomic file replacement, compare-and-set versions, and a
clear side-effect boundary. It must not imply distributed leases, exactly-once
external effects, or a sandbox.

## Decision

We will add a public `AgentRunCheckpoint` data contract and `AgentRunStore`
protocol in `maple.autonomy.runs`, with thread-safe in-memory and atomic
file-backed implementations. An opted-in `AutonomousAgent` run store will
checkpoint the initial prompt and the normalized message cursor after each
completed ReAct step. A run identified by `run_id` can be resumed from the
latest checkpoint, including a paused durable approval: the approved or
denied tool result replaces the pending placeholder before reasoning resumes.

Checkpoint data is JSON-safe, size-bounded, versioned, and restored as data;
no serialized Python object is imported or executed. A checkpoint store is
thread-safe within one process. The agent returns a typed pause result when a
durable approval is pending, and a checkpoint write failure is surfaced rather
than silently allowing an unsafe retry. External side effects remain at-least
once unless the handler supplies its own idempotency contract.

## Alternatives considered

| Option | Pros | Cons | Why not |
|---|---|---|---|
| New bounded `AgentRunStore` using existing JSON-safe messages (chosen) | Clear ownership, local restart support, no dependency, additive API | ReAct state is still local to one host; no distributed lock | Smallest contract that closes the crash-window and approval-resume gap |
| Reuse `SessionStore` for live runs | Fewer types and files | Sessions are conversation history, lack run status/version semantics, and would mix user turns with execution state | Wrong lifecycle and safety boundary |
| Serialize the whole `Goal`/agent object | Captures more Python state | Unsafe/deserialization risk, provider/tool identity drift, arbitrary objects | Violates fail-closed data boundary |
| Distributed database/queue checkpointing | Cross-process scale and leases | New dependency, deployment, auth, and cloud contract | Deferred until local semantics and provider choice are separately approved |

## Consequences

- Positive: a host can recover an in-flight run after a local process restart
  without re-running tool calls already represented in the checkpoint.
- Positive: durable approvals become an explicit pause/resume flow with a
  stable run ID and CAS-protected state.
- Negative / debt accepted: file stores are only coordinated within one
  process; a crash after an external side effect and before its checkpoint can
  still require handler idempotency or manual reconciliation.
- Negative / debt accepted: full ReAct trace replay, distributed leases,
  provider conversation IDs, compaction, and hosted run streaming remain
  follow-on work.
- Invalidation triggers: a requirement for multi-process workers, managed
  tenancy, exactly-once external effects, or provider-native conversation
  persistence reopens this decision and requires a new storage contract.
