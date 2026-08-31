# ADR-098: Atomic Task Reassignment

## Status

Accepted for preview release readiness.

## Context

The scheduler's rebalancer identified moveable `ASSIGNED` tasks but attempted
to claim them through `TaskQueue.assign_task()`. The ownership invariant added
in the completion work correctly rejected that as a duplicate claim, making
rebalancing a no-op even when an overloaded agent had work that had not begun.

## Decision

Add `TaskQueue.reassign_task(task_id, current_agent, new_agent)` as an explicit
ownership-transfer boundary:

- both agent IDs must be non-empty and different;
- the task must exist, be `ASSIGNED`, and be owned by `current_agent`;
- the queue changes the owner to `new_agent` under its existing state lock;
- wrong-owner, missing, invalid-agent, `RUNNING`, and terminal transfers fail
  without changing task state.

`TaskScheduler.rebalance_loads()` uses this transition instead of a normal
assignment claim. It updates the old/new assignment lists and load counters
only after the queue accepts the transfer. `RUNNING` work is intentionally not
movable because the local scheduler has no worker-heartbeat or execution
handoff protocol.

## Data flow and failure behavior

1. The rebalancer identifies an `ASSIGNED` task on an overloaded agent.
2. The queue validates the current owner and destination under one lock.
3. The queue records the new owner and notifies existing task callbacks.
4. The scheduler updates its local old/new load and assignment maps.

If the queue rejects the transfer, the task remains owned by the current agent
and scheduler maps are unchanged for that attempted move. The transition is
local and does not provide distributed fencing, heartbeat reconciliation,
durable queue recovery, or exactly-once external side effects.

## Alternatives considered

| Alternative | Reason not selected |
|---|---|
| Reuse `assign_task()` for the destination | Correctly rejects an already-owned task and cannot express an ownership transfer. |
| Permit reassignment of `RUNNING` work | Could orphan active execution without a heartbeat or handoff protocol. |
| Let the scheduler mutate ownership without the queue lock | Splits the authority boundary and permits races with completion or cancellation. |
| Add a queue-locked explicit transfer for non-running work | Selected: preserves the ownership invariant and repairs local rebalancing with a small contract. |

## Consequences and invalidation triggers

Positive consequences:

- local rebalancing can move work that has not started;
- duplicate and stale ownership transfers fail closed;
- queue ownership changes before scheduler capacity bookkeeping;
- no dependency, network, persistence, or hosted runtime surface is added.

Boundaries:

- the scheduler still has no worker heartbeat or crash-recovery mechanism;
- a task may become stale between planning and transfer, in which case the
  queue rejects the operation and the scheduler leaves that move uncounted;
- active execution handoff and distributed rebalancing remain separate.

Revisit this ADR if running work must migrate, workers can crash without host
reconciliation, or reassignment must cross process boundaries.

## Evidence

Focused scheduler/task-queue regressions cover successful rebalancing ownership
transfer and rejection of reassignment for a `RUNNING` task. Final suite,
package, static, and security evidence is recorded in the slice 153 QA and
review records.
