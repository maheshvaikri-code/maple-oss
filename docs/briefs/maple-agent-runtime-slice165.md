# Project Brief - MAPLE Agent Runtime Slice 165

**Class:** L
**Date:** 2026-08-28
**Owner:** Product Owner
**Problem:** The authenticated handoff transport can create, inspect, accept,
and transition a digest-only handoff, while the local `HandoffStore` already
retains a bounded successful result. A remote target therefore cannot deliver
that result to the source through the transport, and a source cannot retrieve
it without using an out-of-band channel.

## Scope

1. Allow authenticated handoff completion to submit the existing bounded JSON
   result through `POST /v1/handoffs/<handoff_id>/complete`.
2. Add an explicit `GET /v1/handoffs/<handoff_id>/result` route and matching
   `RunClient.get_handoff_result()` operation.
3. Require the host-configured `handoff:result` principal scope for result
   retrieval; ordinary handoff inspection remains result-redacted.
4. Preserve the existing handoff ownership state machine, result defensive
   copying, request/response bounds, and legacy completion without a result.
5. Keep the transport authenticated, host-owned, and provider-neutral.

## Acceptance criteria

1. Existing completion calls without `result` behave exactly as before.
2. A completed handoff may retain a bounded JSON object supplied through the
   authenticated completion route; malformed, non-object, oversized, or
   non-JSON results fail closed without mutating the record.
3. The result route returns only a completed handoff's bounded result and
   target goal metadata; missing, pending, accepted, failed, or result-less
   records return stable bounded errors.
4. A principal with `handoff:read` but not `handoff:result` can inspect
   redacted metadata but cannot retrieve the result; wildcard and family scopes
   retain their documented behavior.
5. `RunClient.complete_handoff(..., result=...)` validates the public input
   boundary, and `get_handoff_result()` validates the handoff identifier.
6. No task/context contents, credentials, raw exceptions, automatic retries,
   broker delivery, scheduler, or exactly-once side-effect claim is added.
7. Existing handoff, server, client, static, package, and tracked-test gates
   remain green.

## Threat sketch

- **Assets:** delegated result payloads, handoff identity, source/target
  ownership, and the host's authenticated result boundary.
- **Entry points:** model/host-provided completion result, handoff ID path,
  bearer token, principal scopes, JSON decoder, and file-backed record store.
- **Worst plausible abuse:** a caller uses a valid transport token to read a
  sensitive target result, submit an oversized or malformed payload, or replay
  a terminal transition. A separate result scope, strict bounds, store-owned
  validation, and immutable terminal-state rules limit those outcomes.

## Non-goals

- Per-agent identity issuance, multi-tenant authorization, or an external
  identity provider.
- Automatic result forwarding, push notifications, broker queues, retries, or
  distributed scheduling.
- Result mutation after completion, result consumption semantics, rollback,
  or exactly-once external effects.
- Raw task/context transfer, hosted workers, or website/publication work.

## Deferred

A durable push/ack protocol, per-principal ownership, and retry-safe external
side effects require separate delivery and idempotency contracts. This slice
provides bounded authenticated result submission plus explicit pull retrieval.
