# ADR-072: Bounded durable approval-outcome replay

**Date:** 2026-08-27  · **Status:** accepted
**Deciders:** Chief Architect

## Context

Durable autonomous runs already persist a pending approval ID and resume after
an operator decision. Approval stores currently mark an approved request as
consumed before invoking the tool handler. If the handler returns and the run
checkpoint cannot be saved, the external effect may have happened while the
approval record has no replayable result; a later resume cannot distinguish a
completed tool from an unobserved one. Retrying that handler automatically
would make the side-effect risk worse.

## Decision

We will let the built-in approval stores persist one bounded terminal tool
outcome after a consumed approval executes. `execute_approved_tool` will return
that recorded outcome for later calls and durable run resume will use it without
invoking the handler again. Outcomes contain only the tool-result content and
error flag, are JSON-safe and size-bounded, and are written idempotently; a
consumed approval without a recorded outcome returns a typed
`APPROVAL_OUTCOME_UNAVAILABLE` error and is never retried automatically. The
contract remains at-least-once for external effects: a crash before outcome
recording can leave the effect uncertain and requires host investigation or a
new explicitly approved action. Custom approval stores without the optional
recording method retain their existing single-use behavior.

## Alternatives considered

| Option | Pros | Cons | Why not |
|---|---|---|---|
| Persist a bounded terminal outcome in the approval record (chosen) | Reuses existing atomic stores; supports sync/async resume; makes the crash window observable and non-repeating after recording | Adds bounded result data to approval records; cannot eliminate a crash between handler return and outcome write | — |
| Re-run consumed handlers on resume | Simple implementation; may recover a missing result | Can duplicate irreversible external effects and violates fail-closed recovery | Rejected for security and correctness |
| Add a distributed transaction or exactly-once coordinator | Stronger cross-store semantics in theory | Requires host/provider protocols, durable coordination, and new infrastructure outside the local library | Deferred until a separately approved hosted contract |

## Consequences

- Positive: recorded approval executions can be replayed across process
  recreation and run-checkpoint save failures without calling the tool again.
- Positive: the unavailable-outcome crash window is explicit, typed, and
  non-retrying rather than silently presented as resumable.
- Negative / debt accepted: approval records retain bounded tool-result text;
  hosts must treat approval storage as sensitive local state and configure
  retention. An external side effect can still be uncertain if the process
  fails before recording the outcome.
- Invalidation triggers: a host-wide transaction/idempotency protocol, a
  durable result store with stronger atomic coupling, or a requirement to
  replay non-JSON tool results would reopen this decision.
