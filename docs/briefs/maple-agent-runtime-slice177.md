# Project/Task Brief - Bounded remote approval push delivery

**Date:** 2026-08-28 · **Class:** L (new public approval and HTTP/library
surface) · **Requested by:** human

## Problem

MAPLE can persist approval requests and expose authenticated list, inspect, and
decision operations, but a remote operator service must poll for new approval
requests. Human-input notifications now have a bounded remote seam; approvals
need the same capability without exporting execution outcomes or conflating
approval authority with notification delivery.

## Scope

- In: add bounded `ApprovalNotification` parsing, optional local notifier hooks
  to the in-memory and file approval stores, a one-shot stdlib HTTP notifier,
  an authenticated receiver route, and a typed `RunClient` operation.
- In: publish the new approval notification contract and preserve existing
  store, decision, lease, and server compatibility.
- **Non-goals:** durable outbound queues, automatic retry, delivery
  deduplication, hosted identity, token issuance, TLS termination, hosted UI,
  approval execution, or exactly-once delivery/effects.

## Acceptance criteria

1. A valid `ApprovalNotification` round-trips through bounded JSON, accepts
   future unknown fields, enforces event/status invariants, and excludes
   `execution_result` and other tool outcomes.
2. New and decided approval records invoke an explicitly configured local
   notifier after persistence; notifier failure returns a typed error while
   the approval record remains authoritative.
3. `HttpApprovalNotifier` makes exactly one bounded POST to a complete
   endpoint, allows loopback HTTP, requires HTTPS elsewhere, and requires an
   explicit `accepted: true` acknowledgement.
4. `POST /v1/approvals/notifications` requires bearer authentication and the
   distinct `approval:notify` scope, validates before callback, returns only
   notification metadata, and never mutates the approval store.
5. Missing auth/scope, malformed or oversized payloads, unavailable or failed
   callbacks, transport failures, and bad acknowledgements produce typed
   failures without retries or hidden side effects.
6. Existing approval lifecycle, lease, server, and client behavior remains
   green; public docs, parity, changelog, plan, QA, review, and package
   evidence are updated.

## Constraints

Stdlib-only runtime; additive APIs; bounded JSON and HTTP bodies; fail-closed
parsing and authorization; no logging of bearer tokens, arguments, or full
notification bodies; no implicit retry; no publication, cloud, or website
action.

## Assumptions

- The notifier endpoint is the complete receiver URL.
- `created`, `approved`, and `denied` are the only approval notification
  events. Consumed approvals and execution outcomes remain local/store-owned.
- A receiver callback is host-owned and returns `Result[None, Error]`.
- Hosts that need durable delivery, replay, or deduplication wrap the notifier
  in their own queue and policy.

**Human confirmed:** no - bounded defaults recorded for review
