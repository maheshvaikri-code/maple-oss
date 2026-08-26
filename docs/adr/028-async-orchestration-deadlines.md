# ADR-028: Deadline and cooperative cancellation for async orchestration

**Date:** 2026-08-25  
**Status:** accepted  
**Deciders:** Chief Architect

## Context

MAPLE's async supervised and consensus paths bounded concurrency and joined
results deterministically, but a caller could not attach a total request budget
or cancel a fan-out without canceling the entire surrounding event loop task.
That left a lifecycle gap: model calls and native async workers could outlive
the request's useful budget.

## Decision

`execute_supervised_async` and `execute_consensus_async` accept additive,
keyword-only `cancellation` and `timeout_seconds` parameters. The timeout is a
single relative budget that starts at the public method boundary and covers
decomposition, member fan-out, result collection, and consensus synthesis.

The orchestrator observes the existing thread-safe `CancellationToken`, cancels
pending native async child tasks, and drains them before returning. Interruptions
are typed as `ORCHESTRATION_CANCELLED` or `ORCHESTRATION_TIMEOUT`. Invalid or
non-positive timeout values fail as `ORCHESTRATION_CONFIG_INVALID`. Default
arguments preserve the existing behavior.

The async path retains its existing executor fallback for sync-only agents.
Python cannot forcibly stop a running worker thread, so cancellation returns
promptly but those handlers must be independently cooperative and idempotent.
This limitation is explicit in the public API rather than represented as hard
termination.

## Alternatives considered

| Option | Pros | Cons | Why not |
|---|---|---|---|
| Request budget plus scoped task cancellation (chosen) | Additive API, bounded cleanup, no dependency | Sync-only threads remain cooperative | Fits MAPLE's existing cancellation primitive and trust model |
| Only rely on outer `asyncio` task cancellation | Minimal code | Does not provide a caller budget and complicates child cleanup | Leaves the lifecycle gap unresolved |
| Force-kill executor threads | Apparent hard stop | Unsafe and not supported by Python; side effects may be left partial | Cannot be an honest framework guarantee |
| Add a distributed cancellation service | Cross-process coordination | New state, deployment, and dependency contract | Deferred with distributed scheduling |

## Consequences

- Positive: async fan-out has a request-wide deadline and explicit cancellation
  errors that callers can handle without parsing exceptions.
- Positive: native async work is canceled and drained within the orchestration
  scope; stable result ordering remains unchanged for successful runs.
- Negative / debt accepted: sync-only executor work may continue after the
  caller receives an interruption result; host handlers own idempotency and
  cooperation.
- Invalidation triggers: distributed agents, provider-native cancellation
  handles, or a requirement for hard isolation of arbitrary code.
