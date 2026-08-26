# ADR-040: Add bounded human-input host notification and authorization hooks

**Date:** 2026-08-26
**Status:** accepted

## Context

Durable human-input records can now be leased safely across local processes,
but a host still needs a bounded way to learn that a request was created or
decided and to authorize the human actor submitting a response. A generic
network service would add transport, identity, delivery, and deployment
contracts that are not required for the local runtime.

## Decision

Add two dependency-free host protocols:

- `HumanInputNotifier.notify(notification)` receives a bounded
  `HumanInputNotification` for `created`, `responded`, and `rejected` events.
  Notifications include request metadata and actor identity, but never the
  submitted response payload.
- `HumanInputAuthorizer.authorize(actor_id, action, request)` returns a typed
  boolean decision. When configured on either human-input store, authorization
  runs inside the record fencing lease before `respond` or `reject`. Missing,
  invalid, denied, exceptional, or malformed authorization fails closed.

`AutonomousAgent.respond_human_input` and `reject_human_input` accept an
optional `actor_id` and forward it to the configured store. Existing local
callers without an authorizer remain compatible. Store consumption remains an
internal runtime transition and does not require an operator actor.

Notification failure is surfaced as `HUMAN_INPUT_NOTIFICATION_ERROR` after
the record has been persisted. The host must inspect the record before retrying;
notifications are not a transactional delivery mechanism. Callback code is
caller-owned and must be bounded, non-reentrant, and safe to run while the
record lease is held.

## Alternatives considered

| Option | Pros | Cons | Why not |
|---|---|---|---|
| Local notifier/authorizer protocols (chosen) | Small dependency-free seam; auth is inside the ownership boundary; easy to test | Caller owns transport, identity, and delivery | Fits the current local durable runtime without claiming hosted support |
| Poll-only host integration | No callback failure path | Delayed UX; no actor authorization hook | Insufficient for interactive approval workflows |
| Embedded HTTP/webhook service | Immediate remote notifications and transport | Adds auth, networking, retries, deployment, and secret-management contracts | Deferred until a hosted operator surface is explicitly scoped |
| Authorization outside the lease | Simpler store code | Approval can become stale before mutation | Violates the record ownership boundary |

## Consequences

Local hosts can integrate a UI, queue, or audit sink and enforce actor-level
authorization without modifying MAPLE's durable record schema. Notification
delivery remains at-most-once per successful mutation attempt and can be
uncertain after a callback failure; polling the authoritative store is the
recovery path. This slice does not provide authentication credentials,
transport encryption, remote identity, multi-round conversations, or
exactly-once external side effects.

## Invalidation triggers

Revisit this ADR before adding remote notification delivery, signed actor
credentials, tenant isolation, multi-round forms, or a hosted operator UI.
