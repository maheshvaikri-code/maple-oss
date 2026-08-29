# Slice 189 brief - owner-safe remote task retry

**Date:** 2026-08-29
**Class:** M
**Role:** Architect / Backend Engineer / Security / QA
**Status:** complete

## Objective

Expose bounded caller-driven retry for failed remote tasks while preserving
queue ownership, retry limits, capacity bounds, and durable local state.

## In scope

- `POST /v1/tasks/{task_id}/retry` under `task:retry`;
- `RunClient.retry_task(task_id, assigned_agent)`;
- an optional owner argument on local `TaskQueue.requeue_task()` and
  `FileTaskQueue.requeue_task()`;
- atomic owner/state checks for failed tasks and stable task responses;
- focused tests, API/README/parity/changelog updates, and release evidence.

## Out of scope

- automatic retries, scheduler loops, worker selection, or backoff policy;
- retry of queued, assigned, running, completed, cancelled, or timed-out work;
- lease revocation, handler execution, queue federation, or hosted workers;
- publication, cloud services, and website work.

## Acceptance criteria

1. An authenticated caller with `task:retry` can retry a failed task only as
   its recorded owner.
2. Retry count and queue capacity remain bounded and authoritative.
3. Invalid owner/state, missing tasks, malformed bodies, and unauthorized
   targets fail closed without mutation.
4. In-memory and durable queues preserve the same owner-safe contract.
5. Existing no-owner local requeue compatibility and all repository gates
   remain green.
6. Clean archive/package evidence is recorded without publication.

## Evidence plan

- focused server and task-management regressions;
- changed-boundary formatting, lint, type, compile, and security checks;
- full workspace suite;
- exact clean archive package/install/doctor gate;
- review/QA artifacts that distinguish explicit retry from automatic retry.
