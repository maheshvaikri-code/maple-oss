# ADR-013: Bounded checkpointed workflow fan-out/fan-in

## Status

Accepted — 2026-08-24

## Context

MAPLE's native workflow runtime supported validated sequential edges,
conditional routing, interruption, and node-boundary checkpoints. Agent
framework parity also requires independent workflow branches to run in
parallel and join before a downstream node consumes their combined state.

The runtime is dependency-free and the current checkpoint contract is a
JSON-safe snapshot. A fan-out implementation must therefore bound resource
usage, avoid nondeterministic state merges, and keep the persistence boundary
explicit. It must not imply process isolation or rollback of side effects made
by user handlers.

## Decision

Add `Workflow.add_fan_out(source, branches, join)` and a
`max_parallel_branches` constructor bound.

- Branch handlers run in a bounded `ThreadPoolExecutor`.
- Each branch receives an independent JSON-safe snapshot of the state emitted
  by the source node.
- Branch outputs must use distinct state keys. Collisions fail the run rather
  than applying order-dependent last-write-wins behavior.
- Branch declaration order controls output merging and `completed_nodes`
  history, while execution remains concurrent.
- The source and all branch outputs are committed in one checkpoint before the
  join node runs. The group counts as one workflow step.
- A branch pause interrupts the run at the group boundary. Resuming repeats
  the source and all branches, so branch handlers must be idempotent when they
  perform external side effects.
- The default limit is eight branches, with a hard configuration ceiling of
  64. The implementation is trusted in-process execution, not a sandbox.

## Alternatives considered

### Sequential branch execution

Rejected because it does not provide the latency benefit or concurrency
semantics expected from a workflow fan-out/fan-in primitive.

### Last-write-wins state merging

Rejected because the result would depend on completion timing and could hide a
data-integrity defect. Callers must use distinct output keys or add an explicit
join node that resolves the values.

### One checkpoint per branch

Deferred. It would require a richer checkpoint schema for pending branch
identity, partial results, retry policy, and side-effect semantics. The current
group checkpoint gives atomic state visibility and a clear at-least-once
recovery boundary.

### Process or container workers

Deferred to a separate execution-boundary project. Threads provide bounded
parallel I/O for trusted handlers but do not isolate memory, imports, or
privileges.

## Consequences

The public workflow API now supports bounded parallel fan-out and deterministic
fan-in without a runtime dependency. A crash or pause before the group
checkpoint can repeat branch work, so callers must design external operations
to be idempotent. Durable replay/history, per-branch retry, cross-process
leases, and hard sandboxing remain open capabilities.
