# ADR-075: Bounded authenticated event batching

- **Status:** Accepted
- **Date:** 2026-08-27
- **Decision owners:** Chief Architect / Backend / Interoperability / Security / Observability

## Context

MAPLE's event transport currently accepts one event per authenticated HTTP
request. That preserves a small failure boundary, but high-frequency lifecycle
telemetry pays one request/response overhead for every already-bounded event.
The local `EventStream` and optional `FileEventJournal` already own redaction,
sequence assignment, retention, and local durability.

## Decision

Add an authenticated `POST /v1/events/batch` route and
`RunClient.publish_events(...)`. A request contains between 1 and 100 event
envelopes, each using the existing `event_type`, `payload`, and optional
`run_id` fields. The server submits each envelope to the configured
host-owned `EventStream` in request order and returns bounded per-item
`published` and `failed` arrays with the original item index. The stream
continues to assign local sequence and timestamp values and to apply its
redaction and payload limits.

Malformed batch structure is rejected before any event is attempted. A valid
batch may have partial success: an individual journal, payload, subscriber, or
exporter outcome belongs to that event, and the caller must inspect every
result. The server performs no retry or deduplication; callers own retry and
idempotency decisions for event delivery.

## Security and failure contract

The route uses the existing bearer authentication, request-body, path, and
response bounds. The maximum of 100 items limits CPU, response, and callback
amplification. Event payloads never bypass the existing stream redaction and
JSON validation. Per-item errors are returned as bounded structured data and
must not include raw request bodies or credentials. The transport remains
loopback by default and does not introduce a remote dependency.

Batching does not provide transactionality: earlier events may be durably
published when a later item fails. It does not provide a remote event log,
fleet aggregation, persistent delivery queue, ordering across clients, or
exactly-once delivery.

## Alternatives considered

1. **Keep one event per request:** rejected as the only transport because it
   adds avoidable request overhead for already-bounded telemetry.
2. **Buffer inside `HttpEventExporter`:** deferred because implicit buffering
   needs lifecycle/flush/backpressure semantics and can hide delivery failure.
3. **Add a broker or telemetry SDK:** deferred; provider, tenancy, retry,
   retention, and operational lifecycle require a separate approved boundary.

## Consequences

Hosts can send bounded event groups and inspect each accepted or failed item
without changing local event ownership. Partial success is explicit and
observable. Operators still need a host-owned queue or durable remote collector
when delivery must survive process failure or network outages.
