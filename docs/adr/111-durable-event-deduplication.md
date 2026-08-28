# ADR-111: Durable Receiver-Side Event Deduplication

**Date:** 2026-08-28
**Status:** accepted
**Deciders:** Chief Architect

## Context

`EventForwarder` intentionally advances a durable source cursor only through
the contiguous acknowledged prefix, so a lost response or cursor write can
redeliver an event. `InMemoryEventDeduplicationStore` protects one receiver
process, but it loses completed claims on restart and cannot coordinate a
second local process. The receiver needs a durable, bounded replay guard while
remaining honest about at-least-once delivery and external side effects.

## Decision

We will add `FileEventDeduplicationStore`, a standard-library JSON store that
retains bounded `(source_id, source_sequence)` claims, a SHA-256 content
fingerprint, expiration time, and only the already-redacted destination event
after completion. Every read-modify-write operation will run under the
existing `DurableRecordLease`, use an atomic temporary-file replacement, and
validate the complete state before returning. Expiration will use persisted
wall-clock timestamps. The store will be usable anywhere the existing
`EventDeduplicationStore` protocol is accepted, but it will claim only local
cross-process durable duplicate suppression, not distributed exactly-once
delivery or exactly-once external effects.

## Data flow and failure modes

```text
forwarded source event + source identity
  -> validate and fingerprint in receiver
  -> durable lease for store directory
  -> load + validate + purge expired records
  -> claim / complete / abort in memory
  -> bounded JSON encode + fsync + atomic replace
  -> release lease
  -> return copied destination event or typed error
```

- Invalid identity, event, fingerprint, clock, JSON, size, or capacity fails
  before a committed mutation.
- A matching completed claim returns its copied destination event; a matching
  pending claim returns `EVENT_DEDUPLICATION_IN_PROGRESS`.
- A different fingerprint for the same source identity returns
  `EVENT_DEDUPLICATION_CONFLICT`.
- Corrupt or oversized state returns `EVENT_DEDUPLICATION_LOAD_ERROR` and is
  never silently repaired.
- A lease acquisition or release failure returns a typed error; callers retain
  the existing at-least-once retry responsibility.

## Alternatives considered

| Option | Pros | Cons | Why not |
|---|---|---|---|
| Bounded JSON file with the existing durable lease (chosen) | No dependency, inspectable state, restart persistence, consistent with current file stores | Serializes operations for one local receiver and rewrites bounded state | Fits the local-first contract and current repository storage patterns |
| SQLite-backed deduplication | Better indexed growth and transactional primitives | Adds a storage schema and operational/versioning surface; does not create distributed coordination by itself | Too much machinery for the bounded local receiver contract |
| One file per source claim | Smaller individual writes and less global serialization | More files, quota accounting, cleanup races, and directory-scan complexity | The fixed bounded state file is easier to validate atomically |
| Keep the in-memory store only | Fast and already implemented | Loses replay protection on restart and across local workers | Does not close the documented durability gap |

## Consequences

- Positive: a restarted or multi-process local receiver can replay a completed
  destination event without publishing it twice within the retained window.
- Negative / debt accepted: the bounded file is not a shared distributed
  service; expiry/capacity can reopen a replay window, and external effects
  remain at-least-once and host-idempotent.
- Invalidation triggers: a requirement for multi-node shared deduplication,
  retention beyond the bounded file, or a formal exactly-once side-effect
  protocol reopens the design for a separate storage/coordination contract.
