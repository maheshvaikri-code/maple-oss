# ADR-100: Ownership-Checked Task Failure

## Status

Accepted for preview release readiness.

## Context

Completion and reassignment now verify task ownership, but workers still had
no corresponding failure acknowledgement. A worker or stale caller could use
the generic status update path, leave scheduler load occupied, or report an
unbounded error. Retry policy was also at risk of being conflated with failure
recording.

## Decision

Add `TaskQueue.fail_task(task_id, assigned_agent, error)` as the local failure
boundary:

- the agent ID must be non-empty and match the recorded owner;
- the task must exist and be `ASSIGNED` or `RUNNING`;
- the error must be a non-empty string of at most `8,192` UTF-8 bytes;
- the queue records `FAILED` and the error through its existing state lock;
- invalid, wrong-owner, missing, and terminal transitions fail without
  mutation.

`TaskScheduler.task_failed()` delegates to this queue transition first, then
releases the scheduler assignment and capacity. It does not automatically
requeue the task; callers explicitly choose the existing bounded
`requeue_task()` operation.

## Data flow and failure behavior

1. A worker reports a task failure with its task ID, owner ID, and error.
2. The queue validates identity, active state, and error size under one lock.
3. The queue records `FAILED` and notifies existing task callbacks.
4. The scheduler removes the assignment and releases one local capacity slot.
5. A host may explicitly request bounded retry admission if appropriate.

If validation fails, queue state and scheduler bookkeeping remain unchanged.
The boundary is local and does not provide automatic retry orchestration,
distributed failure reporting, worker heartbeats, durable queue recovery, or
exactly-once external effects.

## Alternatives considered

| Alternative | Reason not selected |
|---|---|
| Let workers call generic `update_task_status()` | Bypasses ownership and can leave scheduler capacity inconsistent. |
| Automatically requeue every failure | Conflates acknowledgement with retry policy and can create retry storms. |
| Accept arbitrary error payloads | Allows unbounded task-state growth and weakens the persistence boundary. |
| Validate ownership and error bounds, record failure, and require explicit requeue | Selected: separates state truth from retry intent while preserving the local queue contract. |

## Consequences and invalidation triggers

Positive consequences:

- failure state and scheduler capacity remain aligned;
- stale or wrong-owner failure reports fail closed;
- error storage has a finite UTF-8 bound;
- retry remains visible, bounded, and caller-selected.

Boundaries:

- this does not determine whether a side effect occurred before failure;
- process crashes and worker liveness remain host responsibilities;
- distributed retries, durable ownership, and exactly-once effects remain
  separate.

Revisit this ADR if failure reports cross processes, automatic retry becomes a
first-class scheduler policy, or worker heartbeats govern ownership.

## Evidence

Focused regressions cover successful failure acknowledgement, error recording,
wrong-owner rejection, oversized-error rejection, unchanged assignment state,
and explicit separation from retry admission. Final suite, package, static,
and security evidence is recorded in the slice 155 QA and review records.
