# Slice 190 brief - authenticated remote task queue statistics

**Date:** 2026-08-29
**Class:** M
**Role:** Architect / Backend Engineer / Security / QA
**Status:** proposed

## Objective

Expose fixed, read-only queue health statistics through the authenticated task
control plane so remote operators can observe bounded local queue pressure.

## In scope

- `GET /v1/tasks/stats` under `task:read`;
- `RunClient.task_queue_stats()`;
- fixed `QueueStats` counters and finite numeric values;
- generic failure for malformed/unavailable optional queue statistics;
- focused tests, API/README/parity/changelog updates, and release evidence.

## Out of scope

- task payload/result inspection through the stats route;
- distributed aggregation, dashboards, alerts, hosted metrics, or tracing;
- scheduler changes, queue lifecycle changes, worker heartbeats, or leases;
- publication, cloud services, and website work.

## Acceptance criteria

1. An authenticated caller with `task:read` receives the fixed queue stats
   envelope without task contents.
2. Unauthorized callers are rejected before queue access.
3. Malformed/non-finite queue stats fail closed with a stable error.
4. In-memory and durable queues remain compatible with the route.
5. Existing task inspection and all repository gates remain green.
6. Clean archive/package evidence is recorded without publication.

## Evidence plan

- focused server and task-management regressions;
- changed-boundary formatting, lint, type, compile, and security checks;
- full workspace suite;
- exact clean archive package/install/doctor gate;
- review/QA artifacts that state the host-local telemetry boundary.
