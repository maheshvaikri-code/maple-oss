# Project Brief - opt-in remote handoff invocation idempotency

**Date:** 2026-08-28
**Class:** M - authenticated adapter behavior and retry safety
**Requested by:** human continuation

## Problem

`RemoteHandoffTarget` already sends an explicit local `handoff_id` as the
remote agent `run_id`, but a retry after a lost response does not currently
send an idempotency key. A receiver that opts into Slice 171's bounded
invocation store can therefore still execute the same remote handoff twice.

## Scope

- In: an explicit opt-in `RemoteHandoffTarget` mode that uses the supplied
  `handoff_id` as the remote `idempotency_key`.
- In: sync and async adapter paths, bounded local validation, raw/typed client
  compatibility, API/README/parity/changelog updates, and regressions.
- In: receiver configuration guidance using
  `RunServer(agent_invocation_store=...)`.
- **Non-goals:** changing the default adapter behavior, inventing a key when
  no handoff ID exists, remote store provisioning, distributed coordination,
  automatic retries/waiting, push delivery, or exactly-once external effects.

## Acceptance criteria (numbered, testable)

1. Existing `RemoteHandoffTarget` construction and calls remain unchanged by
   default; no idempotency field is sent unless the new opt-in is enabled.
2. With opt-in enabled, a bounded explicit `handoff_id` is sent as both the
   existing remote `run_id` and the remote `idempotency_key`.
3. Opt-in without a `handoff_id` fails before the HTTP client is called with a
   stable typed adapter error; invalid/over-byte IDs also fail closed.
4. A receiver configured with Slice 171's invocation store replays a matching
   remote handoff response and suppresses a duplicate handler call; conflicting
   task/context content remains a conflict at the receiver.
5. Sync and async adapter methods share the same binding, cancellation,
   bounded-result, and remote-error behavior.
6. Public API docs, parity ledger, changelog, release plan, tests, static and
   security checks, and clean-archive packaging are complete.

## Constraints

- Use the existing `RunClient.run_agent(..., idempotency_key=...)` contract;
  add no dependency or remote service.
- The feature is explicit opt-in because a receiver without a configured
  invocation store must fail closed for keyed requests.
- The adapter remains at-least-once across crash windows and does not claim
  exactly-once effects.

## Open questions

- None for the local-first adapter boundary. Automatic key generation or
  caller/tenant identity binding requires a separate approved contract.

**Human confirmed:** continuation of the direct request on 2026-08-28
