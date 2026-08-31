# ADR-124: Optional cross-process notification drain fence

**Date:** 2026-08-28 · **Status:** proposed
**Deciders:** Chief Architect (local host-owned contract)

## Context

The Slice178 outbox coordinates drain calls only within one Python process.
Multiple host workers can therefore make concurrent delivery attempts against
one directory. MAPLE already has a bounded, durable `FileLeaseManager` with
fencing tokens, so the outbox can offer an opt-in coarse owner fence without
inventing a second lease protocol.

## Decision

We will add an optional caller-owned `FileLeaseManager` and bounded TTL to
`FileNotificationOutbox`. A drain acquires a deterministic outbox-wide lease
resource before snapshotting candidates, calls the downstream target outside
the outbox state lock, and releases the lease after the batch. Acquisition or
release failures are typed and fail closed. The lease is not automatically
renewed; if target work outlives the TTL, another holder may acquire the
resource and at-least-once duplicates remain possible. Existing callers with
no lease manager retain Slice178's in-process semantics.

## Alternatives considered

| Option | Pros | Cons | Why not |
|--------|------|------|---------|
| Optional existing `FileLeaseManager` fence (chosen) | Reuses tested fencing and caller-owned storage; additive | Coarse lease and TTL can still permit duplicates | - |
| Always enable a new implicit lease directory | Safer default for local multi-process use | Hidden filesystem ownership and behavior change for existing callers | Preserve backwards compatibility and explicit ownership |
| Per-record delivery leases | Smaller contention window | More state/lease traffic and still no exactly-once effects | Defer until queue workers need that scheduling model |
| No fence | No code/API work | Concurrent local drainers duplicate downstream calls | Does not close the local coordination gap |

## Consequences

- Positive: coordinated local workers can fail fast when another outbox
  drainer owns the durable fence.
- Negative / debt accepted: no renewal, queue worker, distributed consensus,
  or exactly-once side-effect guarantee; a TTL expiry during target work can
  permit duplicate attempts.
- Invalidation triggers: hosted lease service, worker heartbeats, multiple
  independent queue consumers, or exactly-once delivery requirements.
