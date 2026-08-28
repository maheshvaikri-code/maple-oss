# ADR-103: Bounded durable agent-run history

**Status:** Accepted

## Context

`AgentRunStore` persists only the latest checkpoint for a durable ReAct run.
That is sufficient for restart recovery, but it leaves operators without a
bounded local view of the state transitions that led to the current cursor.
The workflow runtime already exposes bounded inspection history, and the
comparison frameworks make checkpoint inspection and time-oriented debugging
visible developer surfaces.

## Decision

Add an optional `AgentRunHistoryStore` protocol and implement its `history()`
surface on the built-in in-memory and file-backed run stores. Every successful
compare-and-set save records a detached `AgentRunCheckpoint` snapshot. The
retention bound defaults to 100 snapshots and is configurable from 1 through
10,000. Results are returned in ascending checkpoint-version order and are
copied again at the read boundary.

The configured bound is the active retention window. A file store may be
restarted with a smaller bound; valid older sidecars are read within the new
window and are trimmed on the next successful save. Snapshots already evicted
by a previous bound cannot be recovered.

`InMemoryAgentRunStore` retains history only for its process lifetime.
`FileAgentRunStore` stores history as an atomically replaced JSON sidecar under
`<directory>/.history/<run_id>.json`; the current checkpoint remains the
authoritative recovery record. History files are validated for JSON shape, run
identity, bounded size, and strictly increasing versions. Corrupt or
contradictory history fails closed with a typed error rather than becoming an
empty successful result.

## Consequences

- Operators can inspect a bounded local sequence of run checkpoints after a
  restart without exposing messages or reasoning traces through the HTTP
  control plane.
- History is inspection data only. It does not re-run handlers, restore an old
  checkpoint, deduplicate side effects, or provide distributed time travel.
- Current-checkpoint replacement and history-sidecar replacement are each
  atomic, but they are not a cross-file transaction. If the current checkpoint
  is durable and the history sidecar cannot be written, `save()` returns
  `RUN_HISTORY_SAVE_ERROR`; callers should inspect the current checkpoint before
  retrying.
- Retention is bounded by snapshot count and by a derived sidecar size limit;
  managed storage, encryption, tenancy, and remote history search remain
  host-owned concerns.

## Rejected alternatives

- **Expose only the latest checkpoint:** preserves the existing crash-recovery
  contract but leaves local transition diagnosis unnecessarily opaque.
- **Add executable replay or restore in this slice:** would require explicit
  handler side-effect, tool replay, approval, and idempotency policies; it is a
  larger security and correctness contract.
- **Use a database or new dependency:** violates the local-first release
  boundary and is not required for bounded local inspection.
