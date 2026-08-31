# Project Brief - durable receiver-side event deduplication

**Date:** 2026-08-28
**Class:** L - public persistence contract, cross-process coordination, and release artifacts
**Requested by:** human

## Problem

The authenticated event receiver can suppress duplicate source events only
while an in-memory deduplication store remains alive. A receiver restart or a
second local worker can therefore accept the same forwarded source event
again, even though the sender's cursor deliberately provides at-least-once
delivery. This leaves a practical replay-protection gap for durable local
deployments.

## Scope

- In: a bounded file-backed `EventDeduplicationStore` that persists source
  identity, content fingerprint, pending/completed state, and the already
  redacted destination event; atomic restart-safe writes; cross-process
  fencing through the existing durable lease boundary; public exports and
  documentation.
- **Non-goals:** distributed database coordination, hosted aggregation,
  exactly-once external side effects, source-payload retention, automatic
  retries, or a change to the existing at-least-once forwarder contract.
- Deferred: a multi-node shared deduplication service, configurable retention
  administration, and end-to-end effect idempotency across external systems.

## Acceptance criteria (numbered, testable)

1. Given a completed claim persisted by one `FileEventDeduplicationStore`,
   when a new instance claims the same source ID and sequence with matching
   content, then it receives the copied redacted destination event without a
   new pending claim.
2. Given a pending claim, when another instance claims the same identity,
   then it receives `EVENT_DEDUPLICATION_IN_PROGRESS`; after an explicit
   abort, a later claim can proceed.
3. Given malformed, conflicting, oversized, expired, or capacity-exhausted
   input, when the store is called, then it returns a stable typed error and
   does not partially mutate the persisted record set.
4. Given two local processes using the same store directory, when they claim
   or complete records concurrently, then the durable lease serializes each
   operation and no committed record is lost; the store remains bounded by
   `max_entries`, `max_bytes`, and `ttl_seconds`.
5. Given a corrupted or path-unavailable store file, when it is read or
   written, then the store fails closed without returning unvalidated event
   data or silently replacing the bad state.
6. The new store is exported from `maple.autonomy` and `maple`, documented
   with a runnable example, and the existing in-memory store and all tracked
   regression gates remain green.
7. The implementation does not claim distributed exactly-once delivery,
   exactly-once side effects, broker semantics, or hosted scheduling.

## Constraints

- Python standard library and the existing `DurableRecordLease` only; no new
  runtime dependency.
- Default limits are at most 10,000 retained claims, 16 MiB persisted state,
  and a seven-day TTL; constructor values are finite and bounded.
- Persist only the fingerprint and redacted destination event. Never retain
  the original source event payload in the deduplication record.
- JSON parsing, event validation, path handling, and atomic replacement must
  fail closed. A rejected operation must not mutate the file.
- Preserve the existing `EventDeduplicationStore` protocol and the
  at-least-once sender/cursor semantics.

## Assumptions (chosen defaults - correct me if wrong)

- The next parity increment should strengthen the existing local receiver
  boundary before attempting hosted infrastructure.
- A file-backed, single-directory store is useful for one host and multiple
  local processes; it is not a distributed coordination service.
- Expiration uses a persisted wall-clock timestamp so a new process can make
  the same retention decision after restart.

## Open questions (blocking - answered before G1)

- None. The brief deliberately does not change the external cloud target or
  the exactly-once side-effect policy.

**Human confirmed:** yes - continuation of the direct request on 2026-08-28
