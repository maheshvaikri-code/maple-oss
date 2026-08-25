# Review — MAPLE agent-runtime slice 35

## Scope

Close the public type-boundary debt in `TaskScheduler` without changing task
selection, assignment, rebalancing, callback, or scheduler-loop behavior.

## Review findings

- Optional scheduler policy and metrics fields now match their existing
  defaults.
- Lifecycle, callback, and scheduler-loop return contracts are explicit.
- The queued-task loop narrows the `Task | None` result before using its ID.
- Unused legacy imports were removed; no scheduling algorithm was changed.

## Decision

Slice accepted as a behavior-preserving type cleanup. Fault-tolerance,
aggregation, and performance-optimizer modules remain separate boundaries.
