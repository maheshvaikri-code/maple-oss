# ADR-094: Bounded Global Task-Queue Admission

## Status

Accepted for preview release readiness.

## Context

`TaskQueue` stores tasks in one `PriorityQueue` per priority. Each physical
queue was constructed with the configured `max_queue_size`, so the effective
total could be up to five times the advertised capacity. A zero capacity also
created Python's unbounded `PriorityQueue`. Status updates did not remove the
physical tuple immediately, so cancelled or completed tasks could remain
eligible for assignment.

These behaviors made admission and assignment depend on priority distribution
and allowed a stale task to cross the execution boundary.

## Decision

Keep the existing local priority queues, but add one lock-guarded queued-item
count and an explicit constructor bound:

- `max_queue_size` must be a non-boolean integer from `1` through `100,000`;
- submission checks the shared count before storing and enqueueing a task;
- successful physical enqueue increments the shared count;
- every physical dequeue decrements it before inspecting the task;
- cancelled, completed, failed, timed-out, or otherwise non-`QUEUED` tuples
  are discarded and never assigned;
- an agent-incompatible tuple is reinserted and restores the count;
- requeue admission checks the shared count before changing task state;
- the existing per-priority `PriorityQueue` full check remains a defensive
  guard, while the shared count defines the public capacity.

The queue's public methods continue to use the existing re-entrant lock and
condition. This protects queue admission, assignment, status transitions, and
requeue state within one process. Direct mutation of public task objects is
not a supported synchronization API.

## Data flow and failure behavior

1. `submit_task()` validates the task type, creates the task, and calls the
   locked enqueue path.
2. The enqueue path rejects capacity exhaustion before adding the task to the
   task map, then marks and physically enqueues accepted tasks.
3. `get_next_task()` removes tuples in priority order. Stale tuples consume
   their physical slot and are dropped; compatible live tuples become
   `ASSIGNED`; incompatible tuples are restored.
4. `requeue_task()` rejects a full global queue before changing retry count,
   status, timestamps, or error. Accepted retries add one new physical tuple.

Capacity failure is returned as a typed `Result` error for submission and
requeue. Invalid constructor capacity raises `ValueError` before any worker or
queue state is created. The queue remains local and in-process; this decision
does not add durable queue storage, distributed worker ownership, remote
scheduling, hard cancellation, or exactly-once external effects.

## Alternatives considered

| Alternative | Reason not selected |
|---|---|
| Keep one independent capacity per priority | The advertised size would not describe total admission, and priority distribution would change resource pressure. |
| Use one shared priority queue and remove the per-priority queues | It would be a larger scheduling rewrite and could change established ordering and task-management integration. |
| Leave stale tuples for consumers to interpret | A consumer could receive a cancelled or completed task, which is unsafe at the assignment boundary. |
| Remove stale tuples during every status update | It would require arbitrary tuple removal from heap-backed queues and adds more mutation work to status transitions. |
| Add a lock-guarded global count with lazy stale-entry discard | Selected: it preserves the existing queue layout, makes admission deterministic, and removes stale entries when they reach the assignment boundary. |

## Consequences and invalidation triggers

Positive consequences:

- capacity is independent of priority distribution;
- queue capacity zero/unbounded behavior is removed from the public contract;
- stale terminal tasks cannot be assigned;
- failed requeues remain retryable after another queued task drains;
- no dependency, network, persistence, or hosted-runtime surface is added.

Boundaries:

- status updates do not synchronously remove physical tuples; capacity is
  released when a consumer drains the stale tuple;
- capacity is per `TaskQueue` instance and process, not a distributed quota;
- callback execution, scheduler policy, retries, and external side effects
  remain separate contracts.

Revisit this ADR if MAPLE introduces durable queue persistence, multiple
processes sharing one queue, remote worker claims, or a scheduler that needs
reservation/lease semantics beyond local tuple admission.

## Evidence

Focused task-management regressions cover constructor validation, capacity
across all priorities, stale cancelled/completed tuples, and full requeue
state preservation. Final package, exact-suite, static, and security evidence
is recorded in the slice 149 QA and review records.
