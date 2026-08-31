# ADR-067: Bounded Authenticated Event Ingestion

## Status

Accepted - preview capability, local-first.

## Context

MAPLE already has a bounded `EventStream` with redaction, ring retention,
subscriber/exporter isolation, local metrics, and an optional
`HttpEventExporter`. The exporter can deliver an event to a host-owned HTTP
sink, but the built-in loopback transport had no matching receiver. That left
remote event delivery as a test-only seam and made it harder to compose the
existing local observability contract across host processes.

The next increment must remain small: accept one bounded event at a time,
require transport authentication, and keep the receiving stream authoritative
for sequence numbers, timestamps, redaction, retention, and failure behavior.
It must not become a hosted telemetry service or imply durable delivery.

## Decision

Add an optional authenticated event-ingestion seam:

- `RunServer(event_stream=..., auth_token=...)` exposes `POST /v1/events`.
- `RunClient.publish_event(event_type, payload, run_id=...)` sends one event
  through the existing bounded JSON transport.
- The route requires `event_type` and `payload`; it accepts an optional
  `run_id` and ignores exporter envelope metadata such as remote sequence and
  timestamp fields.
- The receiving `EventStream.publish(...)` assigns local sequence/timestamp
  values and remains authoritative for redaction, payload limits, callbacks,
  exporters, and local metrics.
- `HttpEventExporter` can target the route, so the existing already-redacted
  exporter envelope has a dependency-free local round-trip path.

The server requires a bearer token whenever an event stream is configured.
Authentication protects transport access only; it does not establish tenancy,
per-agent principals, or an authorization policy.

## Alternatives considered

1. **Trust and retain the sender's sequence/timestamp.** Rejected because
   multiple producers can collide or reorder values, and accepting sender
   metadata would weaken the receiving stream's ordering and timestamp
   authority. The receiver creates fresh local values.

2. **Add batching and durable replay in this route.** Rejected because batch
   framing, deduplication, queue ownership, retry behavior, durable cursors,
   and backpressure need a separate delivery contract. One-event ingestion is
   sufficient to connect the existing exporter without claiming those
   semantics.

3. **Create a new event receiver abstraction beside `EventStream`.** Rejected
   for this slice because it would duplicate redaction, payload validation,
   subscriber isolation, and metrics. The existing stream is the host-owned
   receiver boundary.

## Bounds and failure modes

- Existing server path, authentication, request-body, JSON, and response
  limits apply; the stream's event type, redaction, depth, item, string, and
  payload-byte limits apply after decoding.
- Missing `event_type` or `payload`, malformed JSON values, invalid event
  values, and oversized payloads fail closed with typed `400` responses.
- A missing configured stream returns `503`; a missing or wrong bearer token
  returns `401` before the request body is processed.
- The route performs no retry, queueing, batching, persistence, deduplication,
  fleet aggregation, remote trace search, or exactly-once delivery claim.
- The loopback server does not terminate TLS, issue tokens, or provide
  per-principal authorization. Non-loopback deployment remains host-owned.

## Consequences

MAPLE now has a small authenticated receiver for the existing best-effort HTTP
event exporter. Events cross a host boundary without importing a framework or
duplicating stream semantics, and the receiver cannot be made to adopt a
remote ordering claim.

Remote observability is still incomplete. Hosts needing durable replay,
aggregation, batching, search, or stronger delivery semantics must add a
separately reviewed transport and storage layer.
