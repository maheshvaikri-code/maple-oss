# Slice 185 brief — bounded durable local task queue

**Date:** 2026-08-28
**Class:** L
**Role:** Chief Architect / Backend Engineer
**Status:** proposed

## Objective

Close the local durable-queue gap behind the existing `TaskQueue` and
`TaskScheduler` APIs. A host should be able to restart a local worker without
losing admitted task records or terminal outcomes, while the contract stays
explicitly at-least-once for tasks interrupted during assignment or execution.

## In scope

- a `FileTaskQueue` compatible with the existing `TaskQueue` lifecycle methods;
- bounded JSON-safe task payload, metadata, result, and error persistence;
- atomic state replacement and a caller-selected file path;
- local cross-process fencing around read/modify/write operations;
- restart hydration with `ASSIGNED`/`RUNNING` tasks returned to `QUEUED`;
- preservation of terminal task history until the existing host cleanup policy;
- scheduler-facing assignment, completion, failure, cancellation, requeue, and
  inspection behavior;
- focused tests, public documentation, parity, changelog, and release evidence.

## Out of scope

- hosted or distributed worker scheduling;
- queue federation, automatic retry, lease renewal, or remote delivery;
- exactly-once external side effects or handler replay;
- deleting or compacting user task history automatically;
- new runtime dependencies, cloud services, or website work.

## Acceptance criteria

1. A task submitted to `FileTaskQueue` is recoverable after queue recreation.
2. Persisted queued tasks retain priority/order and terminal records retain
   ownership/result/error state.
3. Restarted `ASSIGNED`/`RUNNING` tasks become queued and are documented as
   at-least-once recovery.
4. State writes are atomic and bounded; malformed, oversized, non-JSON, or
   conflicting state fails closed without silently dropping records.
5. Concurrent local queue instances are fenced during state mutation and
   stale operations cannot overwrite a newer committed state.
6. Existing in-memory `TaskQueue` behavior and scheduler tests remain green.
7. Package, static, security, and clean-archive evidence is recorded without
   publication.

## Threat sketch

Assets are task payloads, terminal results, ownership, and queue ordering.
Entry points are the configured state path, persisted JSON, and concurrent
queue operations. The plausible abuse is path escape, state corruption,
oversized JSON, or a stale worker overwriting a newer task transition. Bounds,
path canonicalization, atomic replacement, strict parsing, and a local fencing
lease contain the boundary; interrupted handlers remain explicitly
at-least-once.

## Evidence plan

- focused `tests/task_management/test_durable_task_queue.py` regressions;
- task-management and full workspace test suites;
- Black, isort, Ruff, mypy, compileall, diff, and source scans;
- clean archive/package install and network-free doctor smoke, with no
  publication, cloud, or website action.
