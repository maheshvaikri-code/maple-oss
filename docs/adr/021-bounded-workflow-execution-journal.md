# ADR-021: Bounded workflow execution journal

**Date:** 2026-08-24  · **Status:** accepted  · **Deciders:** Chief Architect

## Context

MAPLE checkpoints commit only after a workflow node returns and its output is
validated. A process failure after a handler has produced an output but before
the checkpoint commit can cause the handler to run again during recovery. The
existing checkpoint history is an inspection surface and does not provide a
replay boundary.

## Decision

We will add an optional, bounded `ExecutionJournal` to `Workflow`.

- Each node invocation receives a deterministic `WorkflowContext.execution_key`
  derived from run ID, step count, and node name. The journal also stores a
  canonical input digest covering state and resume value.
- After a handler returns a normalized JSON mapping, MAPLE persists that
  mapping to the journal before saving the workflow checkpoint. A subsequent
  invocation with the same key and digest reuses the mapping and skips the
  handler.
- In-memory and atomic file-backed journals are provided with global record,
  per-run record, and record-byte bounds. Invalid, conflicting, or malformed
  records fail closed with typed errors.
- Journal use is opt-in. It narrows the crash-replay window but does not claim
  exactly-once external side effects; handlers that call external systems
  remain responsible for idempotency using `execution_key`.
- Journal records are retained until the host calls `clear(run_id)`; automatic
  retention, cross-process leases, graph-version fingerprints, and distributed
  coordination remain outside this slice.

## Alternatives considered

| Option | Pros | Cons | Why not |
|---|---|---|---|
| Optional bounded journal (chosen) | Dependency-free crash-window recovery; usable with memory or local files | Does not make arbitrary external effects exactly-once; adds a host-owned store | Best incremental contract with explicit limits and honest semantics |
| Re-run every interrupted node | No new state or API | Repeats side effects after a crash | Existing behavior; insufficient parity for durable execution |
| Transactional/external task queue | Stronger delivery semantics | New infrastructure, dependency, and deployment boundary | Requires a separate distributed execution design and human/provider decisions |

## Consequences

- Positive: a handler output can survive a checkpoint-save failure or process
  restart and be reused deterministically on recovery.
- Negative / debt accepted: handlers must still be idempotent for effects that
  happen before journal persistence; journal cleanup and graph-version policy
  are host responsibilities.
- Invalidation triggers: reopen for exactly-once claims, multi-worker leases,
  graph revision fingerprints, automatic retention, or remote journal stores.
