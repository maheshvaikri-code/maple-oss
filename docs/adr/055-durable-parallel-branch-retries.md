# ADR-055: Durable bounded retries for parallel workflow branches

- Status: Accepted
- Date: 2026-08-26
- Owners: MAPLE runtime maintainers

## Context

MAPLE workflows already support bounded retry policies for ordinary nodes. A
fan-out group, however, previously treated a branch error as an immediate group
failure. That made a transient branch dependency materially less reliable than a
sequential node and left no durable retry cursor for a process restart.

The runtime must improve this local behavior without claiming a distributed
scheduler, hard cancellation, or exactly-once external effects. Branch handlers
can perform side effects, so the checkpoint boundary must remain explicit about
at-least-once execution.

## Decision

Reuse the existing `RetryPolicy` for named fan-out branches. A branch retry is
represented in `WorkflowCheckpoint` by:

- `branch_retry_counts`: the number of retries already scheduled per branch;
- `branch_retry_after`: absolute due times for branches with positive backoff;
- `retry_after`: the aggregate due time used by recovery callers.

Branches execute in bounded waves. A failed branch with remaining policy budget
is persisted as `NODE_RETRY_SCHEDULED`, then only the pending branches are run in
the next wave. Each branch receives its current `WorkflowContext.retry_count`.
Successful outputs are merged in declaration order after all branches complete,
so concurrency does not change deterministic state merge behavior. Exhaustion is
reported as `NODE_RETRY_EXHAUSTED` with the branch name and retry metadata.

Branch retry fields are cleared when the fan-out group commits its join boundary.
If a process stops between a branch output and that boundary, the optional
execution journal can reuse normalized output by execution key; without it, the
handler may run again. This is intentionally at-least-once behavior.

## Alternatives considered

1. **Retry the whole fan-out group.** Rejected because it repeats successful
   branches unnecessarily and increases side-effect duplication.
2. **Run branch retries inside worker threads.** Rejected because checkpoint
   writes and retry ordering become harder to reason about, and recovery would
   not have a stable persisted cursor.
3. **Add a hosted/distributed scheduler.** Deferred. It requires an explicit
   transport, authentication, lease, cancellation, and side-effect contract.

## Consequences

Positive:

- transient branch failures receive the same bounded retry semantics as ordinary
  workflow nodes;
- retry progress survives checkpoint-store recreation and recovery;
- successful branches are not retried within the current fan-out execution;
- retry and exhaustion behavior is visible through typed errors and run fields.

Trade-offs:

- local wave execution may wait for the latest branch due time rather than
  providing a distributed ready queue;
- branch side effects remain at-least-once, especially across pause/resume or a
  crash before the join checkpoint;
- percentile telemetry, hosted scheduling, and provider-specific retry
  classification remain separate follow-on capabilities.

## Validation

The release slice adds regression coverage for durable scheduling, retry context,
deterministic completion, and typed exhaustion. Full release evidence is filed in
the corresponding QA and code-review records after all gates complete.
