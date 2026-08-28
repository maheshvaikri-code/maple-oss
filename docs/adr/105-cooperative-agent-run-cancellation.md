# ADR-105: Cooperative cancellation for native agent runs

**Date:** 2026-08-28 · **Status:** accepted
**Deciders:** Chief Architect

## Context

`CancellationToken` already bounds trusted local execution, but the native
ReAct entry points do not accept a caller-owned signal. Durable checkpoints
also do not recognize `cancelled`, so a host cannot distinguish a deliberate
stop from a failure or safely inspect a terminal cancellation. Provider calls
and arbitrary Python handlers cannot be force-killed portably or safely from
the MAPLE process.

## Decision

We will accept an optional `CancellationToken` on native sync/async goal and
resume APIs, check it at every model/tool/reflection/checkpoint boundary, and
propagate it into tool execution. When a running durable loop observes the
signal, MAPLE will persist a terminal `cancelled` checkpoint without pending
interaction IDs, emit bounded `run.cancelled` metadata, and return a typed
`AGENT_RUN_CANCELLED` outcome. Cancellation is cooperative: an in-flight
provider call or ordinary non-executor handler may finish, but no subsequent
model/tool turn starts. Cancellation requested before a paused approval or
human-input record is resolved returns the typed outcome without consuming or
mutating that pending interaction; the checkpoint remains paused for explicit
host control.

## Alternatives considered

| Option | Pros | Cons | Why not |
|--------|------|------|---------|
| Cooperative token at agent boundaries (chosen) | Composes with existing token/executor; deterministic; portable; preserves safety | Cannot interrupt arbitrary in-flight Python/provider work | Fits the current local trust boundary and is honest about effects |
| Hard-kill provider threads/tasks | Faster apparent stop | Unsafe cleanup, leaked effects, provider-specific semantics, broken state | Not a safe portable Python contract |
| Provider-specific abort API | Can stop some network calls earlier | Non-portable, partial coverage, new adapter surface | Separate provider contract is required first |
| Do nothing | No API change | Hosts cannot stop native durable runs or record intent | Fails the runtime parity requirement |

## Consequences

- Positive: native goal hosts can request a bounded stop; durable inspection
  exposes a distinct terminal state; executor-backed side effects retain the
  existing cooperative enforcement path.
- Negative / debt accepted: an in-flight provider or ordinary handler may
  complete; external effects remain at-least-once; paused interaction
  cancellation is intentionally non-mutating; remote token propagation and
  provider aborts remain future work.
- Invalidation triggers: a reviewed provider-neutral abort contract,
  distributed run ownership, or a sandbox with a safe process termination
  boundary would reopen this decision.
