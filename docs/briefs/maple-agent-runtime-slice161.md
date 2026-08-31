# Project Brief - MAPLE Agent Runtime Slice 161

**Class:** L
**Date:** 2026-08-28
**Owner:** Product Owner
**Problem:** Native MAPLE runs now accept cooperative cancellation, but local
agent delegation can hide the caller's signal behind a normal tool handler.
When an `agent-as-tool` or handoff target is itself cancellation-aware, the
parent cannot currently request that child work stop at its own checkpoints.
That weakens cancellation semantics at a core multi-agent boundary and makes
the local delegation surface less predictable under interruption.

## Scope

1. Add an explicit, opt-in cancellation-aware handler contract to `Tool` for
   ordinary synchronous and asynchronous handlers.
2. Propagate the parent `CancellationToken` through `create_agent_tool` and
   `create_handoff_tool` when the target method declares that keyword.
3. Preserve compatibility for legacy targets that do not declare
   `cancellation`; they remain cooperative only at the delegation boundary.
4. Add sync/async regression coverage, public API documentation, an ADR,
   parity-ledger update, changelog entry, and release evidence.

## Acceptance criteria

1. A cancellation-aware synchronous delegated target receives the exact parent
   token and can observe cancellation while the delegation is in progress;
   the parent tool returns the existing typed cancellation error and does not
   expose a child result after cancellation.
2. A cancellation-aware asynchronous delegated target receives the exact
   parent token and observes cancellation; the async parent tool returns the
   same typed cancellation error.
3. Both `create_agent_tool` and `create_handoff_tool` propagate the token to
   native targets while legacy targets without the keyword remain callable
   without a signature error.
4. A cancellation-aware tool cannot be combined with the trusted executor
   path unless the executor contract is extended explicitly; configuration
   fails before execution rather than silently misrepresenting propagation.
5. Existing tool, handoff, agent, run, and server behavior remains green, and
   documentation states that arbitrary in-flight legacy handlers, providers,
   remote targets, and external side effects are not force-killed.

## Non-goals

- Hard-killing Python threads, provider requests, browser sessions, or child
  processes.
- Remote token transport, hosted identity, tenancy, scheduling, or policy
  evaluation.
- Exactly-once execution or rollback of external side effects.
- Introducing a third-party dependency or changing the wire protocol.

## Assumptions

- A target method is cancellation-aware only when its callable signature
  accepts `cancellation` explicitly or through `**kwargs`.
- Legacy targets retain their existing invocation contract; lack of a
  cancellation parameter is surfaced as a documented capability boundary,
  not treated as a hard failure.
- The existing `Tool` post-execution cancellation check remains authoritative
  for targets that do not cooperate.

## Deferred

- Provider-specific abort contracts and remote child-run cancellation remain
  separate reviewed slices.
