# Project/Task Brief - Authenticated Remote Handoff Payload Delivery

**Date:** 2026-08-28 · **Class:** L (new public interoperability surface crossing
the handoff, agent, and authenticated transport boundaries) · **Requested by:**
human

## Problem

MAPLE can persist local handoff ownership and can invoke a host-owned agent over
the authenticated `RunClient` contract, but those surfaces are not connected.
A caller that wants a handoff to cross a process must manually move the task
and context, invoke the remote agent, and finalize the local handoff, which
loses the reusable handoff abstraction and makes failure handling inconsistent.

## Scope

- **In:** A public `RemoteHandoffTarget` that adapts `RunClient` to the existing
  `create_handoff_tool` target contract; bounded task/context/session/run
  forwarding; deterministic remote run identity when a persisted handoff ID is
  available; sync and async target methods; generic failure normalization;
  regression tests, API documentation, parity ledger, changelog, and release
  evidence.
- **Non-goals:** Remote handoff-store mutation, raw payload persistence in
  `HandoffRecord`, automatic retries, queues, scheduling, push notifications,
  remote cancellation, provider selection, multi-principal token issuance,
  distributed coordination, or exactly-once external effects.
- **Deferred:** Remote asynchronous result polling, remote durable run replay,
  cross-host identity federation, and hosted routing policy.

## Acceptance criteria (numbered, testable)

1. Given a valid authenticated `RunClient` and target agent ID, when a caller
   constructs `RemoteHandoffTarget`, then invalid IDs, clients, sessions, and
   control characters are rejected before any request is made.
2. Given a local `create_handoff_tool` with an in-memory or file-backed store,
   when it invokes a `RemoteHandoffTarget` with allowlisted context, then the
   remote handler receives the exact bounded task/context and the local
   handoff transitions through `pending -> accepted -> completed`; the returned
   payload contains the local handoff ID and remote run/goal identity.
3. Given a persisted handoff ID, when the remote target is invoked, then that
   ID is passed as the remote run ID; existing local targets that do not accept
   the new optional keyword remain callable unchanged.
4. Given denied context, malformed or oversized remote output, missing remote
   agent, unauthorized transport, or transport failure, when delivery is
   attempted, then no raw remote payload or exception text is exposed, the
   local handoff is failed when it exists, and no retry is performed.
5. Given an already-cancelled token, when a remote handoff is attempted, then
   no HTTP request is made and a typed cancellation result is returned.
6. Given a declared async remote target, when `execute_async` is used, then
   the same bounds, result shape, error normalization, and no-retry behavior
   apply without blocking the event-loop caller on the HTTP call.
7. Existing handoff, server, client, and tracked repository tests remain green;
   public exports and one runnable documentation example describe the new
   contract and its at-least-once limitation.

## Constraints

- Standard library and existing MAPLE dependencies only; no new runtime
  dependency.
- Preserve `Result<T,E>`, existing handoff ownership semantics, and legacy
  target signatures.
- Reuse `RunClient` validation, HTTPS requirement for authenticated
  non-loopback URLs, response bounds, and server-side `AgentRegistry` bounds.
- Do not retain task/context contents in the local `HandoffRecord`; only the
  existing digests and bounded terminal result remain durable.
- No cloud target is selected; no publication, deployment, or website action.

## Assumptions (chosen defaults - correct me if wrong)

- A remote handoff is a synchronous bounded invocation of the existing remote
  agent route; a returned `completed` run is required for successful handoff
  completion.
- `handoff_id` is the caller-owned idempotency correlation passed as the
  remote `run_id` when a local handoff store is active. The transport itself
  performs no retry or deduplication.
- The configured bearer token and server principal remain host-owned; this
  slice does not invent an identity provider or token issuer.

## Open questions (blocking - answered before G1)

- None. The approved release brief already includes interoperability and
  remote transport improvements, and this slice does not introduce a new
  external service or dependency.

**Human confirmed:** yes - direct continuing request on 2026-08-28
