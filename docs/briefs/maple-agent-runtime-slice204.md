# Slice 204 brief — trusted local task worker

**Date:** 2026-08-29
**Class:** L (new public runtime boundary and task-queue contract)
**Roles:** Product Owner / Chief Architect / Backend / Security / QA / Release

## Problem

MAPLE can admit, assign, start, heartbeat, complete, and fail local tasks, but
there is no standard worker boundary that connects a host-owned handler to
that lifecycle. Each consumer must otherwise reproduce task-type filtering,
ownership transitions, execution bounds, and failure recording, which makes
the local task runtime harder to use and easier to misuse.

## Scope

- In: an explicit trusted local worker, task-type-filtered queue polling,
  one-task execution, bounded timeout/input/output handling through the
  existing trusted executor, cancellation propagation, terminal task
  transitions, public exports, API documentation, and regression tests.
- Out: model-generated code execution, shell/browser/computer use, process or
  container isolation, remote workers, hosted identity, distributed leases,
  automatic retry, background worker threads, and exactly-once effects.
- Deferred: a scheduler-to-worker automatic binding and any worker protocol
  for another process or language.

## Constraints and assumptions

- Handlers are supplied and trusted by the host; they receive a detached
  top-level copy of the task payload and must not be treated as sandboxed.
- The existing `TaskQueue` / `FileTaskQueue` remains the lifecycle authority.
- The existing `TrustedLocalExecutor` remains unchanged and supplies the
  cooperative timeout, JSON bounds, approval, and exception boundary.
- The implementation uses only the Python standard library and existing
  MAPLE types.
- `run_once()` is synchronous and processes at most one task; the caller owns
  any loop or thread.

## Acceptance criteria

1. A worker accepts only a non-empty bounded worker ID, a bounded mapping of
   callable task-type handlers, and valid capability/policy inputs; invalid
   construction fails before queue mutation. Proven by
   `test_trusted_task_worker_rejects_invalid_configuration`.
2. A worker polls only registered task types and matching capabilities. A
   non-matching queued task remains queued and a matching task is atomically
   owned by the worker before handler invocation. Proven by
   `test_trusted_task_worker_filters_unregistered_task_types` and
   `test_trusted_task_worker_respects_capability_filter`.
3. A successful handler receives a detached payload mapping and its bounded
   JSON-compatible result is recorded as `COMPLETED` with the worker as owner.
   Proven by `test_trusted_task_worker_completes_in_memory_task` and
   `test_trusted_task_worker_completes_file_task`.
4. Handler exceptions, handler `Result.err` values, invalid task timeouts,
   non-JSON results, and output-limit failures record `FAILED` with a bounded
   non-secret error and do not invoke a second handler. Proven by
   `test_trusted_task_worker_records_handler_failure_without_raw_exception`,
   `test_trusted_task_worker_records_handler_result_error`,
   `test_trusted_task_worker_does_not_store_handler_error_type_metadata`,
   `test_trusted_task_worker_rejects_invalid_task_timeout`,
   `test_trusted_task_worker_enforces_output_bound`, and
   `test_trusted_task_worker_rejects_non_json_result`.
5. A caller cancellation before polling makes no task mutation; cancellation
   during trusted execution records `CANCELLED` when the owned task is still
   active. The worker never claims forceful thread termination. Proven by
   `test_trusted_task_worker_cancellation_preserves_or_cancels_lifecycle`.
6. `run_once()` accepts only a finite non-negative bounded poll timeout,
   returns `ok(None)` when no registered task is available, and rejects a
   concurrent call on the same worker before queue mutation. Proven by
   `test_trusted_task_worker_poll_bounds_and_empty_result` and
   `test_trusted_task_worker_rejects_concurrent_invocation`.
7. In-memory and file-backed queues retain their existing ownership and
   restart semantics; a completed or failed worker task remains observable
   after file-queue recreation. Proven by the file-worker integration tests
   and the existing task-management suite.

## Release and safety boundary

This slice adds a documented public local API but does not claim parity with a
sandboxed code interpreter or a distributed worker service. Execution remains
trusted-only and cooperative. The execution-isolation gate in Slice 199,
hosted coordination gate in Slice 193, CI policy gate in Slice 200, and
publication approval remain independent release conditions.
