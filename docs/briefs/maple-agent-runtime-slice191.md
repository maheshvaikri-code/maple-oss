# Slice 191 brief - owner-safe authenticated remote task start

**Date:** 2026-08-29
**Class:** M
**Role:** Architect / Backend Engineer / Security / QA
**Status:** complete

## Objective

Complete the bounded remote task-worker lifecycle by allowing the recorded
owner of an assigned task to explicitly transition it to `RUNNING`.

## In scope

- `TaskQueue.start_task(task_id, assigned_agent)`;
- durable `FileTaskQueue` persistence of the same owner-checked transition;
- authenticated `POST /v1/tasks/{task_id}/start` under `task:start`;
- `RunClient.start_task()`;
- owner/state/scope regressions and API/README/parity/release evidence.

## Out of scope

- worker heartbeats, leases, expiry, or crash reconciliation;
- scheduler changes, automatic execution, retries, or polling;
- distributed coordination, hosted identity, or exactly-once effects;
- publication, cloud services, and website work.

## Acceptance criteria

1. Only the recorded owner of an `ASSIGNED` task can start it.
2. Repeated starts, missing tasks, terminal tasks, and malformed requests fail
   closed without mutation.
3. The transition records `started_at` and preserves queue statistics
   accounting.
4. In-memory and durable queues expose the same owner/state contract.
5. Existing task lifecycle and full repository gates remain green.
6. Clean archive/package evidence is recorded without publication.

## Evidence plan

- focused server and task-management regressions;
- changed-boundary formatting, lint, type, compile, and security checks;
- full workspace suite;
- exact clean archive package/install/doctor gate;
- review/QA artifacts that state this is an explicit local lifecycle
  transition, not a lease or liveness guarantee.
