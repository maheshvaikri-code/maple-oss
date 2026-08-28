# Project/Task Brief — Bounded remote human-input push delivery

**Date:** 2026-08-28 · **Class:** L (new public HTTP/library surface across
interaction and transport boundaries) · **Requested by:** human

## Problem

MAPLE can persist human-input requests and notify a host callback in the same
process, but an operator service in another process must currently poll the
authenticated interaction list. That leaves a gap for interactive agent
runs: a persisted request can exist without a bounded, typed delivery path to
the host responsible for presenting it.

## Scope

- In: validate and serialize `HumanInputNotification`; add a dependency-free
  one-shot HTTP notifier; receive notifications through an authenticated
  `RunServer` route; expose a matching `RunClient` method; preserve the
  existing local notifier contract.
- **Non-goals:** durable outbound queues, automatic retry, delivery
  deduplication, approval notifications, token issuance, identity federation,
  TLS termination, hosted operator UI, or exactly-once delivery/effects.
- Deferred: approval-specific notification records and a durable distributed
  notification broker remain separate slices.

## Acceptance criteria (numbered, testable)

1. Given a valid `HumanInputNotification`, `to_dict()` followed by
   `from_dict()` returns equivalent bounded data and does not include response
   values; future unknown fields are ignored. Proven by notification model
   round-trip tests.
2. Given an explicitly configured `HttpHumanInputNotifier` and a receiver
   `RunServer`, each persisted `created`, `responded`, and `continued`
   transition makes one bounded POST and the receiver callback observes the
   typed notification. Proven by loopback sender/receiver integration tests.
3. Given missing bearer authentication, a missing `interaction:notify`
   scope, malformed/oversized input, or an unavailable receiver callback, the
   route returns a typed failure and does not invoke the callback. Proven by
   adversarial transport tests.
4. Given a timeout, HTTP failure, invalid acknowledgement, or callback
   failure, the sender returns a typed error without retrying; persisted local
   interaction state remains authoritative. Proven by transport-failure and
   persistence tests.
5. Existing custom `HumanInputNotifier` implementations and stores continue
   to receive the same local notification objects and preserve their existing
   error behavior. Proven by the current interaction-host regression suite.
6. Public API documentation, parity status, changelog, review, QA, and
   release-plan artifacts describe the bounded semantics and non-claims.

## Constraints

Stdlib-only runtime; additive Python and HTTP APIs; JSON request/response
bounds; loopback HTTP or HTTPS for non-loopback endpoints; finite timeout;
fail-closed parsing and authorization; no implicit retry; no external
publication or cloud action.

## Assumptions (chosen defaults — correct me if wrong)

- The notifier endpoint is the complete receiver URL, not a base URL to which
  MAPLE appends a path.
- The receiver acknowledges callback acceptance with HTTP 200 and a bounded
  JSON `{"accepted": true}` response.
- The sender makes exactly one request per local notification callback. An
  ambiguous network result is reported as a delivery error and is not retried
  by MAPLE.
- Hosts that need durability, deduplication, or retries wrap the notifier in
  their own queue and policy.

## Open questions (blocking — answered before G1)

- None. Approval-specific push delivery and hosted identity are explicitly
  deferred rather than silently included.

**Human confirmed:** no · 2026-08-28 (bounded defaults recorded for review)
