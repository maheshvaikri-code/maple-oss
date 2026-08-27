# ADR-076: Bounded durable event forwarding

- **Status:** Accepted
- **Date:** 2026-08-27
- **Decision owners:** Chief Architect / Backend / Interoperability / Security / Observability

## Context

MAPLE can now persist a bounded local event window and deliver authenticated
single events or batches, but a process or network failure between those
operations can leave a host without a resumable delivery position. The local
stream already exposes explicit cursor expiry, and the authenticated batch
route already returns indexed partial acknowledgements. The missing boundary is
a small host-owned pump that combines those contracts without becoming a
broker or silently promising exactly-once effects.

## Decision

Add an opt-in `EventForwarder` that reads at most 100 retained events from a
host-owned `EventStream`, sends them through an `EventBatchSender`, and saves a
cursor only through the contiguous prefix acknowledged by the destination.
Provide `HttpEventBatchSender` for one bounded authenticated HTTP request and
`InMemoryEventCursorStore` plus atomic, fenced `FileEventCursorStore` for
cursor ownership. Repeated calls are explicit; the forwarder never retries in
the background, never skips an unacknowledged event, and accepts that a lost
response or cursor write can cause already-accepted events to be sent again.

## Security and failure contract

- Source events are read through the existing bounded stream cursor and the
  HTTP sender re-applies payload redaction before serialization.
- Batch requests, responses, timeout, endpoint, and bearer-token handling use
  the existing bounded HTTP exporter policy; non-loopback HTTP is rejected.
- A malformed or incomplete acknowledgement fails closed and leaves the
  cursor unchanged. A cursor older than the retained source window returns
  `EVENT_CURSOR_EXPIRED` instead of silently losing events.
- Remote per-item error messages are not copied into the local report; only a
  bounded remote error type is retained. No request retry, remote queue,
  deduplication, transaction, ordering across forwarders, or exactly-once
  external side-effect guarantee is provided.

## Alternatives considered

| Option | Pros | Cons | Why not |
|---|---|---|---|
| `EventForwarder` + durable cursor (chosen) | Reuses existing stream, journal, auth, and batch contracts; small and inspectable | At-least-once delivery; callers schedule calls | Fits the local-first release boundary while making restart/retry state explicit |
| Implicit buffering inside `HttpEventExporter` | Convenient for callers | Hidden queue lifecycle, shutdown, backpressure, and failure semantics | Would obscure delivery state and make loss/retry behavior implicit |
| Add a broker or telemetry SDK | Richer routing, retries, and fleet aggregation | New dependency/provider, tenancy, retention, and operational contracts | Requires a separate approved infrastructure and dependency decision |

## Consequences

- Positive: hosts can resume bounded remote aggregation after process restart,
  inspect indexed partial delivery, and preserve source gaps explicitly.
- Negative / debt accepted: duplicate remote events remain possible, one call
  forwards only one bounded window, and separate processes need host-level
  coordination if duplicate forwarding is unacceptable.
- Invalidation triggers: a requirement for exactly-once effects, remote
  deduplication, fleet-wide ordering, automatic scheduling, durable remote
  retention, or principal/tenant scopes reopens this decision as a new
  transport or infrastructure design.
