# ADR-136: Owner-safe remote task start

**Status:** Accepted for Slice191
**Date:** 2026-08-29

## Context

The authenticated task control plane can claim, complete, fail, cancel, and
explicitly retry work. A claim records `ASSIGNED`, but remote workers have no
explicit way to record that execution has begun. This leaves the existing
`RUNNING` state and its start timestamp inaccessible through the remote worker
boundary.

## Decision

Add `TaskQueue.start_task(task_id, assigned_agent)` as an atomic owner-checked
transition from `ASSIGNED` to `RUNNING`. The transition uses the queue's
existing status accounting and records `started_at`. `FileTaskQueue` executes
the same operation inside its existing fenced read/modify/write wrapper.

Expose the operation as `POST /v1/tasks/{task_id}/start` and
`RunClient.start_task(...)`, requiring the dedicated `task:start` scope. The
server validates the task ID and actor policy before invoking the queue; the
queue remains authoritative for existence, ownership, and lifecycle conflicts.

## Consequences

- remote workers can report an explicit running state;
- existing queue statistics accounting remains consistent with the new state;
- ownership and lifecycle checks remain in the selected queue implementation;
- repeated, wrong-owner, missing, queued, and terminal transitions fail
  without mutation;
- no lease, heartbeat, timeout monitor, automatic retry, scheduler, handler
  execution, distributed coordination, or exactly-once side-effect guarantee
  is introduced;
- the durable queue still normalizes interrupted running work to `QUEUED` on
  restart under its existing explicit at-least-once contract.
