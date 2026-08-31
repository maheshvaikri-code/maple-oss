# Project/Task Brief - Optional cross-process notification drain fencing

**Date:** 2026-08-28 · **Class:** M (additive lease option on the Slice178
outbox) · **Requested by:** human

## Problem

Slice178 makes notification delivery durable and explicit, but its default
thread lock only coordinates drainers inside one process. Two local worker
processes pointed at the same outbox can both call a downstream target. Hosts
that already use MAPLE's durable file lease manager need an opt-in fence for
one outbox-wide drain owner.

## Scope

- In: accept an optional caller-owned `FileLeaseManager` and bounded lease TTL
  on `FileNotificationOutbox`; acquire one deterministic outbox-wide resource
  before a drain and release it after the attempt batch.
- In: return typed unavailable/release failures and preserve existing behavior
  when no lease manager is supplied.
- In: add concurrency regressions and update public/release documentation.
- **Non-goals:** automatic renewal, background workers, distributed service
  discovery, queue federation, exactly-once delivery, or exactly-once external
  effects.

## Acceptance criteria

1. A configured lease manager fences a second process/worker from draining the
   same outbox while the first drain owns the bounded lease.
2. Lease acquisition happens before target calls; target calls remain outside
   the outbox state lock; release is attempted after success, failure, and
   typed drain errors.
3. Lease acquisition/release failures return typed errors without sending a
   notification or hiding an already committed drain result.
4. Existing no-lease callers and all Slice178 persistence, deduplication,
   bounds, and failure semantics remain compatible.
5. The TTL is finite and bounded, and documentation states that work longer
   than the TTL can still permit duplicate delivery.

## Constraints

Stdlib runtime plus the existing MAPLE `FileLeaseManager`; additive API;
fail-closed lease ownership; no automatic renewal or retry; no secrets or
notification payloads in errors/logs; no external publication, cloud, or
website action.

## Assumptions

- Hosts that need cross-process fencing provide a `FileLeaseManager` rooted at
  shared local durable storage and coordinate the outbox directory identity.
- The lease is a coarse drain-owner fence, not a per-notification delivery
  receipt. A downstream call can outlive the TTL and still be duplicated.

**Human confirmed:** no - bounded defaults recorded for review
