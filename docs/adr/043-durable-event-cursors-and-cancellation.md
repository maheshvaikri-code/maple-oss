# ADR-043: Durable event cursors and cooperative cancellation

- Status: Accepted
- Date: 2026-08-26
- Owners: Chief Architect / Backend / Security / QA

## Context

MAPLE already exposed a bounded, redacted `EventStream` with snapshots and
blocking waiters. Consumers that reconnect or process events incrementally
still needed a small state contract: a cursor that can be persisted, a bounded
read that advances it, and an explicit error when ring retention has already
evicted the requested position. Waiters also needed to observe the existing
cooperative cancellation primitive without adding a transport dependency.

## Decision

Add the JSON-safe `EventCursor` and `EventBatch` values. `EventStream.read`
accepts an optional cursor and a limit no larger than the configured ring
capacity, returning the retained events and the next cursor. If a cursor is
older than the retained window, the read fails with `EVENT_CURSOR_EXPIRED`
and reports only sequence metadata so the host can choose an explicit replay
policy.

Extend `EventStream.wait_for` with an optional object exposing
`is_cancelled() -> bool`. Cancellation is checked before waiting and at a
bounded polling interval; cancellation or malformed cancellation state returns
a typed error. Existing snapshot, subscriber, redaction, and lifecycle-event
behavior remains unchanged.

## Consequences

- Hosts can persist `EventCursor.to_dict()` and resume local event consumption
  without silently skipping evicted events.
- Reads remain bounded by the configured ring, and stale cursors fail closed
  instead of inventing a replay source.
- Cooperative cancellation works with MAPLE's existing `CancellationToken`
  while preserving synchronous callback and wait APIs.
- This is a local cursor contract, not a durable broker, remote stream,
  provider-token stream, or hosted telemetry exporter.

## Rejected alternatives

- **Silently start at the oldest retained event:** hides data loss from the
  consumer and makes replay correctness impossible to assess.
- **Persist stream state inside `EventStream`:** couples the in-process event
  contract to filesystem or database policy that belongs to the host.
- **Add an asyncio or broker dependency:** expands the transport boundary before
  MAPLE has an approved hosting contract.
