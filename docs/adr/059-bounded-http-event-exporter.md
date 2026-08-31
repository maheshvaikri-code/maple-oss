# ADR-059: Bounded HTTP Event Exporter

- Status: Accepted
- Date: 2026-08-26
- Decision owners: Chief Architect, Backend, Observability, Security, QA

## Context

MAPLE's `EventStream` already redacts and bounds lifecycle events before
retention or delivery, and its exporter seam isolates sink failures from an
agent run. The comparison runtimes expose broader tracing/export surfaces, but
adding an unbounded remote sink would turn observability into a reliability,
privacy, and dependency problem.

## Decision

Add the dependency-free `HttpEventExporter` as an optional synchronous
`EventExporter` implementation.

- It POSTs one already-redacted `AgentEvent.as_dict()` JSON object per call and
  accepts only 2xx responses. The request body and response body are bounded,
  and every network call has a finite timeout.
- It accepts only `http` or `https` endpoints without userinfo, query strings,
  fragments, or control characters. Non-loopback endpoints require HTTPS.
- An optional bearer token is sent only as an `Authorization` header. Tokens
  are validated for header safety and are never placed in endpoint URLs.
- It performs no automatic retries, queues, persistence, batching, or
  deduplication. Delivery is best-effort and failures are raised to the
  existing `EventStream` isolation boundary, which counts the exporter failure
  and preserves the local event.
- The exporter does not claim fleet aggregation, hosted trace search, exactly-
  once delivery, or protection against a host that intentionally sends a
  manually constructed unredacted event directly to it. Normal `EventStream`
  delivery remains the redaction boundary.

## Rejected alternatives

- A third-party HTTP client would add runtime dependency and audit surface for
  a small standard-library boundary.
- Background batching would require queue ownership, shutdown semantics,
  backpressure, persistence, and retry/idempotency rules that are not defined
  by `EventExporter`.
- Silent remote retries would duplicate telemetry and make exporter latency or
  external effects ambiguous.

## Consequences

Hosts can connect the existing redacted event stream to a compatible HTTPS
collector without writing transport glue. The synchronous call is visible in
local publish latency and should be placed behind a host-owned queue when the
collector may block. Authentication issuance/rotation, tenant authorization,
certificate policy, batching, durable replay, and aggregation remain host-owned
follow-on contracts.
