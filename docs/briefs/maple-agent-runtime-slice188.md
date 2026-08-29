# Slice 188 brief - owner-safe remote task cancellation

**Date:** 2026-08-28
**Class:** M
**Role:** Architect / Backend Engineer / Security / QA
**Status:** proposed

## Objective

Complete the authenticated remote task lifecycle with an owner-safe
cancellation operation that reuses queue-side atomic state transitions.

## In scope

- `POST /v1/tasks/{task_id}/cancel` under `task:cancel`;
- `RunClient.cancel_task(task_id, assigned_agent)`;
- an optional owner argument on local `TaskQueue.cancel_task()` and
  `FileTaskQueue.cancel_task()`;
- queued cancellation, assigned/running owner checks, typed conflicts, and
  bounded request validation;
- focused tests, API/README/parity/changelog updates, and release evidence.

## Out of scope

- force-stopping handlers or revoking worker leases;
- automatic retries, scheduler changes, queue federation, or hosted workers;
- durable distributed cancellation, identity federation, or exactly-once
  external effects;
- publication, cloud services, and website work.

## Acceptance criteria

1. An authenticated caller with `task:cancel` can cancel an unassigned queued
   task for an allowed agent.
2. Assigned or running tasks can be cancelled only by their recorded owner.
3. Terminal tasks, missing tasks, malformed bodies, and unauthorized targets
   fail closed without mutation.
4. In-memory and durable queues preserve the same owner-safe contract.
5. Existing local cancellation compatibility and all repository gates remain
   green.
6. Clean archive/package evidence is recorded without publication.

## Evidence plan

- focused server and task-management regressions;
- changed-boundary formatting, lint, type, compile, and security checks;
- full workspace suite;
- exact clean archive package/install/doctor gate;
- review/QA artifacts that state the non-interrupting cancellation boundary.
