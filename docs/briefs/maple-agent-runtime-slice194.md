# Slice 194 brief - owner-safe task heartbeat signal

**Date:** 2026-08-29
**Class:** L
**Role:** Chief Architect / Backend / Interop / Security / QA / Release
**Status:** proposed

## Objective

Add a small, explicit liveness signal to the existing local task lifecycle so
an assigned worker can report that it is still active without changing task
ownership or allowing MAPLE to infer distributed liveness.

## In scope

- an optional `Task.heartbeat_at` UTC Unix timestamp;
- owner-checked `TaskQueue.heartbeat_task()` for `ASSIGNED` and `RUNNING`
  tasks;
- durable `FileTaskQueue` persistence with legacy-record compatibility;
- authenticated `POST /v1/tasks/{task_id}/heartbeat` under `task:heartbeat`;
- `RunClient.heartbeat_task()` and the documented task envelope field;
- bounded validation, monotonic timestamp handling, regressions, and package
  evidence.

## Out of scope

- heartbeat expiry, timeout decisions, reassignment, scheduler action, lease
  renewal, worker registration, distributed coordination, or hosted liveness;
- handler execution, retry policy, federation, exactly-once effects, cloud,
  publication, and website changes.

## Acceptance criteria

1. Only the recorded owner can heartbeat an `ASSIGNED` or `RUNNING` task.
2. Rejected, missing, terminal, queued, malformed, and oversized operations
   do not mutate task state or durable bytes.
3. Repeated or out-of-order observations never move `heartbeat_at` backward.
4. In-memory and file-backed queues expose the same behavior, and existing
   durable records without the new field remain readable.
5. The authenticated route enforces `task:heartbeat`, principal agent policy,
   exact request fields, and stable task errors.
6. Public docs explicitly state that the signal is telemetry only and makes no
   distributed liveness or exactly-once claim.
