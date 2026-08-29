# ADR-138: Owner-safe task heartbeat signal

**Date:** 2026-08-29
**Status:** proposed
**Deciders:** Chief Architect

## Context

The local task queue now exposes owner-safe claim, start, completion, failure,
cancellation, retry, statistics, and durable restart behavior, but a worker
has no explicit way to report activity during a long `ASSIGNED` or `RUNNING`
operation. A timestamp can improve host-owned inspection and telemetry, but it
must not be interpreted as proof of worker liveness or used to trigger
distributed scheduling decisions.

## Decision

We will add an optional `Task.heartbeat_at` timestamp and an owner-checked
`heartbeat_task()` operation to both queue implementations, plus an
authenticated `task:heartbeat` transport route and client method. The
operation accepts only the recorded owner and active `ASSIGNED`/`RUNNING`
states, stores the greatest observed Unix timestamp, and returns the normal
bounded task envelope. Durable readers accept legacy records that omit the
field and writers emit it. The field is telemetry only: no expiry, lease
renewal, timeout, reassignment, scheduler action, distributed ownership, or
exactly-once effect is inferred.

## Alternatives considered

| Option | Pros | Cons | Why not |
|--------|------|------|---------|
| Add a typed heartbeat field and explicit owner-safe operation (chosen) | Small public contract; durable; inspectable; monotonic under duplicate delivery | Does not solve failure reconciliation by itself | — |
| Store the value in task metadata | No record-shape change | Weakens schema clarity and makes the field host-controlled payload | Rejected: liveness telemetry is a first-class task attribute |
| Add automatic expiry/reassignment now | Addresses crash recovery in one feature | Requires lease authority, scheduler semantics, race handling, and side-effect policy | Rejected: belongs to the gated distributed-coordination contract |

## Consequences

- Positive: workers can expose bounded activity telemetry across local and
  authenticated transport boundaries; duplicate/out-of-order updates cannot
  regress the stored timestamp.
- Negative / debt accepted: hosts still need an explicit policy to interpret
  stale heartbeats; no automatic action is provided.
- Compatibility: legacy durable task records load with `heartbeat_at=None`;
  new records include the additive field; existing task operations retain
  their behavior.
- Invalidation triggers: reopen this decision when a scheduler, lease
  authority, tenant boundary, or distributed failure-reconciliation contract
  is approved.
