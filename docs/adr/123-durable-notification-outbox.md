# ADR-123: Bounded durable notification outbox

**Date:** 2026-08-28 · **Status:** proposed
**Deciders:** Chief Architect (additive, local-first contract)

## Context

The human-input and approval notification seams currently make one bounded
delivery attempt. A receiver outage or process restart can therefore leave a
persisted local event without a delivery attempt that can be resumed. The
outbox must improve restart behavior without changing the source stores or
pretending that a local file gives distributed exactly-once effects.

## Decision

We will add a bounded stdlib-only file-backed outbox that stores canonical
typed notification payloads under deterministic SHA-256 identities, retains
pending and delivered records, and exposes explicit bounded draining. Enqueue
is atomic and does not call the network. Drain calls the host-provided
notifier outside the state lock, durably records success, and retains a
sanitized failure for a later explicit attempt. Human-input and approval
adapters will implement their existing notifier protocols. The contract is
at-least-once: an interrupted success mark may cause a duplicate, while
automatic retry, cross-process lease ownership, purge, identity federation,
and exactly-once external effects remain host-owned or deferred.

## Alternatives considered

| Option | Pros | Cons | Why not |
|--------|------|------|---------|
| Bounded atomic file outbox (chosen) | No dependency; restartable; inspectable; works with existing notifier seams | Local coordination and retention remain host responsibilities | - |
| SQLite queue | Stronger local transactions and indexing | Adds schema/migration and dependency-policy surface for a small additive seam | Deferred until query, lease, or retention needs justify it |
| Background retry worker | Better hands-off availability | Hidden scheduling, retry, shutdown, and duplicate policy | Explicit host drain keeps ownership visible |
| Delete delivered records | Small directory | Loses deterministic deduplication after restart | Retain records until a future explicit retention contract exists |

## Consequences

- Positive: persisted notifications survive process restart, can be drained
  explicitly, and share one bounded contract across both notification types.
- Negative / debt accepted: at-least-once delivery, no automatic retry, no
  cross-process drain lease, bounded retained records, and host-owned
  downstream side effects.
- Invalidation triggers: multiple independent drainers, fleet-level queue
  coordination, purge/retention requirements, hosted identity, or a need for
  exactly-once effect claims.
