# ADR-130: Bounded durable local task queue

**Status:** Proposed
**Date:** 2026-08-28
**Decision owners:** Chief Architect / Backend / Security / QA

## Context

MAPLE's `TaskQueue` provides bounded in-process admission, assignment, and
ownership-checked lifecycle transitions. A process restart currently removes
queued and terminal records, leaving the scheduler parity gap visible against
agent frameworks with durable task/workflow state.

## Decision

Add `FileTaskQueue`, a `TaskQueue` subclass using a caller-selected JSON state
file. The state contains a version marker and bounded task records. Payload,
metadata, result, and error values must be JSON-safe and fit the configured
per-task and whole-file byte limits. Writes use a temporary file in the
canonical parent directory, flush plus `fsync`, then `os.replace`.

Each public state operation hydrates the current state under a local
cross-process `FileLeaseManager` fence, performs the existing in-memory
transition, and atomically persists the result. The queue path is resolved and
required to remain within its configured parent; the lease state lives in a
private sibling directory derived from that path. Lease acquisition failures,
unreadable state, malformed records, and persist failures return bounded
errors. A failed persist restores the pre-operation in-memory state.

On hydration, `QUEUED` tasks remain queued and terminal records retain their
state. `ASSIGNED` and `RUNNING` tasks are reset to `QUEUED`, clear their
ephemeral owner/start time, and remain eligible for redelivery. This is an
explicit local at-least-once recovery boundary; it does not replay handlers or
make external effects exactly once. The queue does not run the inherited
background cleanup thread, so durable terminal history is retained until the
host explicitly removes or replaces the state file.

The class preserves the existing scheduler method names and `Result` return
shapes. No new dependency is introduced; `FileLeaseManager` and the standard
library provide fencing and atomic persistence.

## Alternatives considered

1. **Modify `TaskQueue` to always write disk.** Rejected because it would add
   I/O and persistence policy to existing in-memory callers.
2. **Use SQLite or a new queue dependency.** Rejected for this bounded local
   contract; it would add schema/migration and dependency scope before a
   hosted/distributed queue decision exists.
3. **Persist only queued IDs.** Rejected because terminal outcomes and
   ownership are part of scheduler inspection and recovery truth.

## Consequences

Positive:

- queued work and terminal task history survive local restart;
- existing scheduler-facing calls can use a durable implementation;
- malformed or oversized state fails closed instead of being silently lost;
- cross-process local mutations are fenced and stale writers are contained.

Negative:

- every operation performs bounded local file I/O;
- interrupted assignments/runs may be delivered again after restart;
- this is not a distributed queue, worker lease, scheduler, retry service, or
  exactly-once external-effect protocol.

## Verification

Tests must cover restart hydration, priority/order, terminal preservation,
in-flight requeue, atomic persistence, malformed/oversized/non-JSON state,
path bounds, lease denial, persist rollback, scheduler compatibility, and
concurrent local instances. Package evidence is recorded after the clean
archive gate.
