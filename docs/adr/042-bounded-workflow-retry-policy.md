# ADR-042: Bounded per-node workflow retry policy

- Status: Accepted
- Date: 2026-08-26
- Owners: Chief Architect / Backend / Security / QA

## Context

MAPLE workflows already checkpointed node-boundary state and exposed general
retry primitives, but a node failure immediately terminated the workflow.
Framework parity requires a workflow-native retry decision that survives local
process recovery without turning arbitrary handlers into unbounded or
exactly-once execution.

## Decision

Add the immutable `RetryPolicy` value with `max_retries` capped at eight,
non-negative `base_delay_seconds`, and a capped maximum delay of 60 seconds.
`Workflow` accepts policies through `retry_policies=` and exposes
`set_retry_policy`. A policy is attached to ordinary node handlers; unknown
policy nodes fail workflow validation.

`WorkflowCheckpoint` persists `retry_counts` and an optional `retry_after`
timestamp. On a handler exception or invalid node output, MAPLE:

1. checks the node's configured retry budget;
2. persists `NODE_RETRY_SCHEDULED`, the incremented retry count, and the
   bounded retry timestamp before sleeping or invoking the handler again;
3. exposes the current retry count through `WorkflowContext`; and
4. persists `NODE_RETRY_EXHAUSTED` as the terminal error after the final retry.

Recovery honors an unexpired persisted `retry_after` before invoking the node.
Successful nodes clear the scheduled timestamp while retaining retry counts for
run inspection. Existing workflows without policies retain immediate failure
behavior. Parallel fan-out branches are intentionally excluded from this
persisted per-node policy until branch-level coordination is specified.

## Consequences

- Transient ordinary-node failures can recover with a deterministic bounded
  budget and inspectable checkpoint state.
- A persisted retry schedule closes the process-crash window between deciding
  to retry and the next handler invocation, but it does not make handler side
  effects exactly once.
- Node handlers may still run more than once. External effects require handler
  idempotency keys, transactions, or host-owned coordination.
- Retry delays can block the local workflow call for at most the configured
  60-second cap per retry; callers needing asynchronous scheduling need a
  separate host scheduler contract.
- Fan-out remains bounded trusted-local execution and retains its existing
  pause/recovery side-effect caveat.

## Rejected alternatives

- **Retry every node by default:** changes existing failure behavior and can
  amplify permanent failures.
- **Persist arbitrary exception objects:** violates the JSON-safe checkpoint
  boundary and can expose sensitive runtime data.
- **Claim exactly-once execution from checkpointing:** a handler can fail after
  an external side effect and before its output is committed.
