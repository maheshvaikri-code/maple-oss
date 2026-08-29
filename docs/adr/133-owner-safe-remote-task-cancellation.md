# ADR-133: Owner-safe remote task cancellation

**Status:** Proposed
**Date:** 2026-08-29
**Decision owners:** Chief Architect / Backend / Security / QA

## Context

Slice 186 and Slice 187 expose authenticated remote task submission,
inspection, claiming, completion, failure, and non-blocking claim-next. The
underlying queues already support local cancellation, but a remote worker has
no authenticated cancellation route. Exposing the existing unrestricted local
method would allow a caller to cancel another worker's assigned task.

## Decision

Add `POST /v1/tasks/{task_id}/cancel` and
`RunClient.cancel_task(task_id, assigned_agent)` under a new `task:cancel`
scope. The request body contains only the assigned agent. The queue performs
the ownership check and cancellation transition under its existing mutation
lock: an unassigned queued task may be cancelled by the authorized agent, an
assigned or running task requires its recorded owner, and terminal tasks or
owner mismatches fail with a typed conflict.

The optional owner argument on the local queue method preserves the existing
unrestricted local `cancel_task(task_id)` compatibility while giving remote
callers an atomic owner-safe path. `FileTaskQueue` persists the same transition
through its existing durable fencing boundary.

## Explicit boundary

This is a bounded lifecycle operation, not a distributed cancellation
protocol. It does not interrupt handler execution, revoke leases, retry work,
delete task records, coordinate hosts, or provide exactly-once external side
effects. A remote cancellation acknowledgement describes queue state only;
hosts remain responsible for cooperative worker shutdown.

## Verification

Tests cover authenticated scope and principal policy, queued cancellation,
owner matching for assigned work, terminal-state rejection, durable queue
compatibility, malformed input, and preservation of existing local behavior.
