# Project/Task Brief - Bounded durable notification outbox

**Date:** 2026-08-28 · **Class:** L (new public persistence and delivery
surface) · **Requested by:** human

## Problem

Human-input and approval notifications now have bounded authenticated push
seams, but their current one-shot behavior can lose a notification during a
receiver outage or process restart. MAPLE needs a local, explicit durability
boundary that can be attached to either notification type without silently
claiming distributed delivery or exactly-once side effects.

## Scope

- In: add a stdlib-only file-backed notification outbox with deterministic
  payload identity, bounded records/queue, restart loading, explicit draining,
  failure retention, and typed reports.
- In: add typed human-input and approval outbox adapters that satisfy the
  existing notifier protocols and can be passed to either approval or
  interaction store.
- In: preserve the existing one-shot HTTP notifiers, local notifier hooks,
  store authority, and public documentation/release evidence.
- **Non-goals:** background workers, automatic retries, distributed leases,
  hosted identity, queue federation, destructive retention/purge, exactly-once
  delivery, or exactly-once external effects.

## Acceptance criteria

1. A valid notification is atomically persisted before `notify()` returns;
   duplicate canonical payloads are deduplicated across process restarts.
2. A fresh outbox instance loads typed pending notifications from disk, while
   malformed, conflicting, oversized, or unsafe records fail closed without
   being silently repaired.
3. An explicit bounded `drain()` sends pending records outside the outbox
   lock, marks successful delivery durably, retains failed records for a later
   explicit attempt, and returns a bounded typed report.
4. Queue limits reject new records with a typed error; the implementation does
   not silently delete pending or delivered records to make space.
5. Human-input and approval adapters preserve their existing notifier object
   contracts and integrate with the corresponding built-in stores.
6. Public API documentation, parity status, changelog, plan, review, QA, and
   release evidence describe at-least-once delivery and all non-claims.

## Constraints

Stdlib-only runtime; additive API; atomic local writes; finite bounds; no
network calls while holding the outbox state lock; no bearer-token or full
payload logging; no implicit retry; no publication, cloud, or website action.

## Assumptions

- One host-coordinated drain worker owns a directory at a time. If multiple
  processes drain the same directory concurrently, downstream duplicates are
  possible and remain the host's responsibility.
- Delivered records remain in the bounded directory to support deterministic
  deduplication; no purge API is added in this slice.
- A downstream notifier returning success means the host accepted the
  notification. A crash between downstream success and the durable delivered
  mark can cause a later duplicate.

**Human confirmed:** no - bounded defaults recorded for review
