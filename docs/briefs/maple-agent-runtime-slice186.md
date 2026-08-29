# Slice 186 brief — authenticated remote task-queue control plane

**Date:** 2026-08-28
**Class:** L
**Role:** Chief Architect / Backend Engineer
**Status:** proposed

## Objective

Expose the existing bounded `TaskQueue` lifecycle through a small authenticated
process-boundary control plane. A host should be able to submit, inspect,
claim, complete, and fail work from another local process while preserving
queue-side ownership checks and the optional `FileTaskQueue` local durability.

## In scope

- optional authenticated `RunServer(task_queue=...)` configuration;
- bounded task admission, listing, inspection, and lifecycle routes;
- additive `RunClient` submit/list/inspect/claim/complete/fail methods;
- separate principal scopes for each task operation;
- exact agent and capability allowlist enforcement at the task boundary;
- stable typed errors that do not leak queue internals;
- focused regressions, API/README/parity/changelog updates, and release evidence.

## Out of scope

- distributed scheduling, worker heartbeats, leases, federation, or hosted queues;
- automatic retry, polling, atomic submit-and-claim, or queue idempotency;
- handler execution, sandboxing, or side-effect orchestration;
- exactly-once external effects or a claim that HTTP delivery is transactional;
- new dependencies, cloud services, publication, or website work.

## Acceptance criteria

1. A configured queue is inaccessible without authentication and route scopes.
2. Valid task records round-trip through submit/list/inspect/claim/complete.
3. Queue ownership and principal target/capability policies are enforced.
4. Invalid bounds and malformed query/body/result values fail before mutation.
5. Queue implementation errors do not expose filesystem or callback details.
6. Existing autonomy, task-management, static, and package gates remain green.
7. Clean archive/package evidence is recorded without publication.

## Threat sketch

Assets are task payloads, metadata, results, failure text, queue capacity, and
worker ownership. Entry points are authenticated HTTP requests, query strings,
and queue implementations. The risks are unauthorized inspection or mutation,
oversized/non-JSON data, capability-policy bypass, ownership races, and leaked
durable-queue internals. Scope checks happen before body parsing; exact
principal policies are checked before queue mutation; JSON, text, response,
and queue bounds remain finite; queue-side claims remain atomic; and internal
queue errors are normalized.

## Evidence plan

- `tests/autonomy/test_server.py` remote-task regressions;
- autonomy and full workspace test suites;
- Black, isort, Ruff, mypy, compileall, diff, and secret/dangerous-construct scans;
- clean archive/package install, no-dependency import, and network-free doctor;
- independent code-review and QA artifacts, with no publication or website action.
