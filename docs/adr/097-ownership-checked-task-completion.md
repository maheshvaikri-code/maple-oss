# ADR-097: Ownership-Checked Task Completion

## Status

Accepted for preview release readiness.

## Context

`TaskScheduler.task_completed()` previously changed only scheduler-local load
maps. The authoritative `TaskQueue` record remained `ASSIGNED`, and an unknown
task or unrelated agent could be acknowledged successfully. That allowed task
state and scheduler capacity to diverge.

## Decision

Add `TaskQueue.complete_task(task_id, assigned_agent, result=None)` as the
queue-side completion boundary:

- the agent ID must be non-empty and match the recorded owner;
- the task must exist and be `ASSIGNED` or `RUNNING`;
- the queue records `COMPLETED` and the optional result while holding its
  existing state lock;
- wrong-owner, missing, empty-owner, and terminal transitions fail without
  changing task state.

`TaskScheduler.task_completed()` delegates to this queue transition first. It
removes the task from the agent assignment list and decrements local load only
after the queue accepts completion. A failed completion leaves scheduler load
and assignment state unchanged.

## Data flow and failure behavior

1. A worker calls `TaskScheduler.task_completed()` with its task and agent IDs.
2. `TaskQueue.complete_task()` validates ownership and the active state under
   the queue lock.
3. The queue records the terminal state and result, including existing
   completion timing/callback behavior.
4. The scheduler releases its local assignment and capacity bookkeeping.

The transition is local and in-process. It does not establish distributed
leases, durable queue recovery, worker heartbeats, force cancellation, retry
policy, or exactly-once external side effects.

## Alternatives considered

| Alternative | Reason not selected |
|---|---|
| Keep completion as scheduler-only bookkeeping | Leaves the queue record stale and permits ownership mismatches. |
| Let any caller update the task status directly | Does not bind a terminal transition to the assigned worker. |
| Add a distributed completion protocol | Requires durable ownership, fencing, transport, and side-effect policy outside this local slice. |
| Validate and complete under the existing queue lock, then release scheduler load | Selected: preserves the current local architecture and gives one authoritative transition. |

## Consequences and invalidation triggers

Positive consequences:

- local task status and scheduler capacity stay aligned after completion;
- wrong-owner acknowledgements fail closed;
- result recording uses the existing bounded task-state path;
- no dependency, network, persistence, or hosted runtime surface is added.

Boundaries:

- callers that update the queue directly must use `complete_task()` when they
  need scheduler ownership semantics;
- the method does not prove the worker actually performed an external effect;
- crash recovery, heartbeats, reassignment, and distributed exactly-once
  behavior remain separate.

Revisit this ADR if completion must cross processes, survive queue-store
restarts, reconcile worker crashes, or coordinate external side effects.

## Evidence

Focused scheduler/task-queue regressions cover successful completion, result
recording, running-state completion, wrong-owner rejection, missing-task
failure, and repeated terminal transition failure. Final suite, package,
static, and security evidence is recorded in the slice 152 QA and review
records.
