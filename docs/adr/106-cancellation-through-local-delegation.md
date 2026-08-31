# ADR-106: Cooperative cancellation through local delegation

**Date:** 2026-08-28
**Status:** accepted
**Deciders:** Chief Architect

## Context

Slice 160 added a caller-owned `CancellationToken` to native agent runs and
propagated it through the regular tool and executor boundaries. The local
`agent-as-tool` and handoff helpers still invoke child methods as ordinary
callables, so a child `AutonomousAgent` cannot receive the parent's signal
while it is running. The parent tool's post-call check is too late for a
cooperative child that can stop earlier at its own model, tool, or checkpoint
boundaries.

## Decision

Add an explicit `Tool(accepts_cancellation=True)` contract for non-executor
sync/async handlers. Such handlers receive the keyword-only token, including
`None` when no caller signal was supplied. The delegation helpers opt into the
contract and pass the token to target methods only when their inspected
signature declares `cancellation` or `**kwargs`. Legacy targets are invoked
with their original arguments and remain compatible, but cannot observe the
parent signal during their own work.

The executor path rejects `accepts_cancellation=True` at configuration time:
the existing executor contract supervises a token but does not inject one into
handler kwargs, and silently pretending otherwise would violate the boundary.

## Data flow and failure modes

```text
parent agent token
  -> Tool.execute / execute_async
  -> cancellation-aware delegation handler
  -> signature-qualified child method
  -> child cooperative checkpoints
  -> child result or cancellation
  -> parent post-call cancellation guard
```

- A pre-cancelled parent is rejected by the existing tool boundary before a
  child method or handoff store mutation begins.
- A child that accepts the token may stop and return a cancellation outcome;
  the parent tool still applies its existing post-call cancellation guard.
- A legacy child does not receive an invented keyword and may finish its
  in-flight work; this is explicitly cooperative, not a hard-kill promise.
- Signature inspection failure conservatively uses the legacy invocation and
  therefore does not claim token propagation.
- Handoff ownership records and external effects remain at-least-once; this
  slice does not add rollback or exactly-once semantics.

## Alternatives considered

| Option | Pros | Cons | Why not |
|---|---|---|---|
| Explicit opt-in handler keyword with signature-gated delegation (chosen) | Small additive contract; preserves legacy targets; makes propagation testable | Targets must opt in; introspection can be unavailable for unusual callables | Fits the local Python boundary and is honest about cooperation |
| Always pass `cancellation` to every handler | Simple implementation | Breaks existing handlers and collides with caller argument names | Not backward compatible |
| Store the token in global/thread-local state | No signature changes | Hidden shared state, poor async semantics, difficult ownership and tests | Violates explicit data-flow and concurrency rules |
| Hard-kill child threads/tasks | Apparent immediate stop | Unsafe cleanup, leaked side effects, provider-specific behavior | Not a safe portable Python contract |

## Consequences

- Native child agents can now participate in the same cooperative cancellation
  boundary as their parent.
- Existing legacy delegation remains source-compatible but has a clearly
  narrower cancellation guarantee.
- The executor API remains unchanged and cannot claim handler-level token
  injection until separately designed.

**Invalidation triggers:** a revised executor callback contract, a reviewed
remote child-run protocol, or a safe process-isolation boundary would reopen
this decision.
