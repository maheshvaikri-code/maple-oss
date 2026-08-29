# Slice 187 brief — non-blocking remote claim-next

**Date:** 2026-08-28
**Class:** M
**Role:** Architect / Backend Engineer
**Status:** complete

## Objective

Give an authenticated remote worker a bounded way to claim the next queued
task it can handle, without requiring a caller-side list/filter/claim loop.

## In scope

- `POST /v1/tasks/claim-next` under `task:claim`;
- `RunClient.claim_next_task(assigned_agent, capabilities=...)`;
- bounded capability validation and exact requirement matching;
- deterministic priority/creation/task-ID candidate ordering;
- retrying only bounded ownership races through queue-side atomic claims;
- focused tests and API/README/parity/changelog/release evidence.

## Out of scope

- blocking remote long-polling, worker heartbeats, leases, or scheduler loops;
- automatic retry, fairness guarantees, queue federation, or hosted workers;
- handler execution, sandboxing, cloud services, publication, or website work;
- exactly-once external effects or atomic submit-and-claim.

## Acceptance criteria

1. A compatible worker claims the highest-priority available task.
2. Incompatible tasks are left queued and no-work returns `task: null`.
3. Capability and exact worker-agent principal policies are enforced.
4. Ownership races do not overwrite a winning worker and do not leak internals.
5. Existing task-control routes and all repository gates remain green.
6. Clean archive/package evidence is recorded without publication.

## Evidence plan

- focused `tests/autonomy/test_server.py` claim-next regressions;
- autonomy/task-management and full workspace suites;
- changed-boundary static/security/compile checks;
- clean archive/package install and network-free doctor;
- review/QA artifacts with no cloud, publication, or website action.
