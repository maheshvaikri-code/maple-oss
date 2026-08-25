# ADR-016: Bounded workflow checkpoint history

## Status

Accepted — 2026-08-24

## Context

The workflow runtime persisted only the latest checkpoint. That is sufficient
for recovery, but workflow operators and evaluators also need to inspect state
transitions, understand where a run paused or failed, and prepare future replay
tools without changing the recovery contract.

## Decision

Add `HistoryCheckpointStore`, a bounded decorator around any existing
`CheckpointStore`.

- Every successful save is copied into an immutable in-process history list.
- `history(run_id, limit=...)` returns bounded snapshots in checkpoint-version
  order, with deterministic limits and JSON-safe copies.
- The wrapped store remains the source of truth for load/recovery and all
  optimistic version checks.
- The decorator does not execute node handlers, replay side effects, persist
  history across process restarts, or provide cross-process coordination.

## Alternatives considered

### Add replay execution now

Rejected because node handlers may perform external side effects and the
runtime does not yet have replay-safe effects, idempotency keys, or a dry-run
contract.

### Change every checkpoint backend schema

Deferred. A decorator provides the inspection contract without breaking the
existing `CheckpointStore` protocol or forcing all storage backends to support
history simultaneously.

### Keep only the latest checkpoint

Rejected because it prevents operators from diagnosing transitions and keeps
evaluation/replay tooling blind to intermediate state.

## Consequences

Workflow hosts can inspect bounded current-process history while retaining any
existing in-memory or file-backed recovery store. Durable history, time travel,
replay-safe effects, and production run servers remain follow-on capabilities.
