# ADR-148: explicit trusted local task worker boundary

**Date:** 2026-08-29
**Status:** accepted bounded local contract
**Deciders:** Chief Architect; Product Owner scope from the continuation request

## Context

The local task queues already provide bounded admission, ownership-checked
state transitions, durable file persistence, and restart recovery. They do
not provide a standard way for a host to bind trusted task handlers to those
transitions. A worker that claims an arbitrary queued task could incorrectly
fail work belonging to another handler set, while a worker that runs handlers
without the queue transitions could lose ownership and terminal-state
accounting.

## Decision

We will add `TrustedTaskWorker`, a synchronous one-task-at-a-time boundary
that accepts a host-owned mapping of task types to trusted Python handlers.
The worker will pass its registered task types and capabilities into a new
optional queue polling filter, claim and start the selected task through the
existing queue authority, execute the handler through the unchanged
`TrustedLocalExecutor`, and complete, fail, or cancel the owned task through
owner-checked transitions. The worker will use only local standard-library
mechanisms, will reject invalid configuration before polling, and will leave
looping, threading, scheduling, retries, remote delivery, isolation, and
side-effect semantics to their existing owners.

## Alternatives considered

| Option | Pros | Cons | Why not |
|---|---|---|---|
| Explicit `TrustedTaskWorker` with filtered one-shot polling (chosen) | Small public boundary; preserves queue authority; cannot claim unknown task types; easy to test and embed in a host loop | Caller owns looping; trusted in-process handlers remain non-sandboxed | — |
| Add handler execution inside `TaskScheduler` | Automatic local flow and fewer host calls | Couples scheduling policy to handler registry, complicates durable restart and cancellation, and makes scheduler ownership harder to reason about | Keeps two lifecycle owners in one component and expands the scheduler contract unnecessarily |
| Spawn a process/container per task | Stronger isolation potential and independent worker lifetime | Requires an isolation target, filesystem/network policy, serialization protocol, cleanup contract, and security review | Explicitly belongs to the gated Slice 199 execution-isolation project |
| Do nothing | No new API or compatibility surface | Every host reimplements filtering and lifecycle transitions; task execution remains disconnected | Does not address the local runtime gap |

## Consequences

- Positive: local task execution has one documented lifecycle path for both
  memory and file queues; unregistered task types remain available to other
  workers; task failures are bounded and observable.
- Negative / debt accepted: handlers execute in the worker process and may
  outlive a cooperative timeout in a Python thread; this is not sandboxing,
  force termination, automatic retry, or exactly-once effects.
- Invalidation triggers: a requirement for untrusted code, hard termination,
  multi-process workers, automatic scheduling/retry, or cross-host identity
  reopens this decision under the execution-isolation or hosted-coordination
  gates.
