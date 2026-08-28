# Project Brief - bounded remote agent invocation idempotency

**Date:** 2026-08-28
**Class:** L - public authenticated transport and durable local state
**Requested by:** human

## Problem

An authenticated caller may retry a remote agent invocation after a timeout or
connection interruption, but the current control plane gives the host no
shared request identity with which to distinguish a retry from a new task.
The same handler can therefore execute twice, even when the caller intended
one logical request. This creates an avoidable duplicate-side-effect boundary
for remote composition and capability routing.

## Scope

- In: an optional bounded idempotency key on named-agent and capability-routed
  invocation requests.
- In: host-owned in-memory and file-backed claim/complete/abort stores that
  retain only a request digest and bounded normalized response envelope.
- In: concurrent duplicate suppression, same-key content conflict detection,
  bounded expiry/capacity, raw/typed client support, and authenticated server
  integration.
- In: regressions, public API documentation, parity ledger, changelog, and
  release evidence.
- **Non-goals:** exactly-once external effects, distributed coordination,
  automatic retries, failover, queueing, identity federation, idempotency for
  resume/cancel routes, or server-side execution of user code outside the
  existing host-owned handler boundary.
- Deferred: push notifications, hosted/multi-node deduplication, and a
  provider-specific idempotency adapter.

## Acceptance criteria (numbered, testable)

1. A caller can supply an optional bounded idempotency key to named-agent and
   capability-routed requests; absent keys preserve the current wire shape and
   execution behavior.
2. With a configured in-memory store, two identical concurrent requests share
   one claim: one executes, a completed retry replays the bounded response,
   and an in-flight duplicate returns a typed conflict without invoking the
   handler twice.
3. Reusing a key with a different target or normalized request returns a
   conflict and does not invoke the handler or mutate the completed record.
4. A configured file-backed store atomically preserves completed response
   envelopes across a new store instance, rejects malformed/oversized state,
   and evicts or expires only bounded records without exposing raw request
   payloads beyond the retained response envelope.
5. Missing store configuration, invalid keys, invalid response data, claim
   races, and storage failures fail closed with stable machine errors; no
   handler invocation occurs before a valid claim.
6. Raw client methods remain compatible, typed client methods validate replayed
   envelopes, capability routing retains selected-agent identity, and existing
   named-agent behavior remains green.
7. Public API docs, changelog, parity/release artifacts, focused regressions,
   full tracked tests, static/security checks, and clean-archive packaging
   pass.

## Constraints

- Use the Python standard library and existing `Result`, JSON, authentication,
  and `DurableRecordLease` contracts; add no dependency.
- Keys, target IDs, digests, records, responses, TTLs, and file state have
  explicit finite limits. No request payload or credential is logged or
  retained as an idempotency key.
- Claim-before-handler and complete-after-normalization are the only supported
  ordering. A completion-storage failure is surfaced; the handler is never
  silently retried.
- The feature is opt-in. It improves bounded retry behavior but does not
  claim exactly-once external side effects, especially across crash windows or
  separate stores.

## Threat sketch

Assets touched: idempotency keys, request fingerprints, normalized agent
responses, handler execution counts, and local deduplication files. Entry
points are client-supplied keys and request fields, concurrent authenticated
HTTP calls, and file-store contents. The worst plausible abuse is memory/disk
exhaustion, replaying a response for the wrong request, or using a key to
confuse two callers. Bounded records, canonical request digests, atomic
claim/complete state, fencing leases, detached response copies, scope checks,
and fail-closed conflicts contain the blast radius.

## Open questions

- None for this local-first, host-owned contract. Distributed idempotency,
  caller identity binding, and exactly-once side effects require separate
  approved contracts.

**Human confirmed:** continuation of the direct request on 2026-08-28
