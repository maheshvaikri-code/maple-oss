# ADR-095: Lifecycle-Safe Local Scheduler Assignment

## Status

Accepted for preview release readiness.

## Context

`TaskQueue.get_next_task()` removes a physical tuple and marks its task
`ASSIGNED` before `TaskScheduler` selects an agent. When selection failed, the
scheduler changed the status back to `QUEUED` without adding a tuple back to a
priority queue. The task then appeared pending in task storage but could never
be consumed again. Manual scheduling also had no atomic ownership guard, so
two scheduler callers could both observe a task before either assignment was
recorded.

## Decision

Add an atomic queue-side assignment claim and make scheduler failure rollback
use the existing bounded retry boundary:

- `TaskQueue.assign_task(task_id, assigned_agent)` runs under the queue lock;
- empty agent IDs, missing tasks, terminal states, and already-owned tasks
  fail without mutation;
- a `QUEUED` task, or a just-dequeued `ASSIGNED` task with no owner, can be
  claimed exactly once;
- successful claims set the owner and notify the existing task callbacks;
- `TaskScheduler` updates its load/assignment bookkeeping only after the queue
  claim succeeds and does not hold its scheduler lock while callbacks execute;
- when the scheduler loop cannot find or assign an agent, it records `FAILED`
  with the scheduling error and calls `TaskQueue.requeue_task()`;
- retry count and `max_retries` remain the existing bound for repeated
  scheduler failures; a failed requeue remains terminal if the limit or queue
  capacity rejects it.

The implementation remains local and in-process. It does not introduce a
durable scheduler journal, distributed lease, remote worker claim, or exactly-
once effect guarantee.

## Data flow and failure behavior

1. The scheduler obtains a task from the queue or receives a queued task for
   manual scheduling.
2. Agent selection runs using the existing registry, capability matcher, and
   policy.
3. The scheduler calls `assign_task()`. The queue lock serializes ownership;
   a competing scheduler receives an error after the first claim.
4. On successful claim, scheduler load and assignment maps are updated under
   the scheduler lock.
5. On selection/assignment failure after dequeue, the loop records the error,
   marks the task failed, and re-enters the existing bounded retry admission.

The rollback is physical: it creates a new priority-queue tuple and restores
the queue's global count. A status-only transition is not considered a
successful rollback. If retry admission rejects the task, the failure remains
observable as a terminal task result rather than an apparently queued task
that has no physical queue entry.

## Alternatives considered

| Alternative | Reason not selected |
|---|---|
| Set status back to `QUEUED` after scheduler failure | Leaves no physical queue tuple, causing silent task loss. |
| Let every scheduler caller check status before assignment | Separate check and write operations race under concurrent schedulers. |
| Hold the scheduler lock across queue status callbacks | It couples scheduler state to user callback execution and can create lock-order risk. |
| Add a durable or distributed scheduler claim protocol | It expands persistence, lease, ownership, and deployment scope beyond this local hardening slice. |
| Claim through the queue lock, then update scheduler bookkeeping after the claim | Selected: ownership is serialized at the authoritative queue boundary while scheduler bookkeeping remains locally guarded and callbacks are outside its lock. |

## Consequences and invalidation triggers

Positive consequences:

- one task cannot be assigned to two owners through concurrent scheduler
  callers;
- scheduler failures restore a physical queue entry through bounded retry;
- queue callbacks retain the existing notification behavior;
- no dependency, network, persistence, or hosted-runtime surface is added.

Boundaries:

- scheduler failure retries consume the task's existing retry budget;
- queue-side ownership and scheduler-side load bookkeeping are separate local
  structures and can still require host-level reconciliation after a process
  crash;
- task callbacks remain best-effort as defined by `TaskQueue`;
- durable queues, distributed leases, hosted scheduling, hard cancellation,
  and exactly-once external effects remain separate.

Revisit this ADR if scheduler assignment must survive process failure, span
multiple queue instances, coordinate remote workers, or reserve capacity with
leases.

## Evidence

Focused lifecycle regressions cover physical rollback, duplicate ownership,
atomic assignment, and invalid owner input. Final suite, package, static, and
security evidence is recorded in the slice 150 QA and review records.
