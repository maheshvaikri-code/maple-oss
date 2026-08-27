# ADR-068: Bounded Authenticated Event Inspection

## Status

Accepted - preview capability, local-first.

## Context

Slice 121 connected the existing `HttpEventExporter` to an authenticated
host-owned `EventStream` through one-event `POST /v1/events` ingestion. A
remote consumer could publish into that stream, but it still could not inspect
the retained redacted events through the same dependency-free transport.

`EventStream.read(...)` already provides the required local semantics: a
serializable cursor, bounded batches, explicit retention-gap detection, and
receiver-owned event envelopes. The next increment should expose only that
existing contract and should not turn the loopback server into a durable log or
hosted telemetry service.

## Decision

Add an authenticated read seam:

- `RunServer(event_stream=..., auth_token=...)` exposes
  `GET /v1/events?after=<sequence>&limit=<limit>`.
- `RunClient.read_events(cursor=..., limit=...)` uses the same route and
  returns the existing `EventStream.read(...)` batch envelope under `batch`.
- `after` defaults to sequence `0`; `limit` defaults to the smaller of the
  stream capacity and the remote batch bound of `1,000`.
- Query parameters are strict: only one `after` and one `limit` are accepted;
  unknown, duplicate, malformed, negative, or over-bound values fail with a
  typed `400` response.
- The event stream remains authoritative for redaction, retention, sequence,
  timestamps, and cursor expiry. Returned events are already redacted.

## Alternatives considered

1. **Add a new remote event model.** Rejected because it would duplicate the
   existing cursor and batch semantics and create a second redaction boundary.

2. **Return a snapshot without a cursor.** Rejected because consumers could
   silently skip evicted events and could not make bounded incremental reads.

3. **Add durable remote replay or a hosted search API.** Rejected because
   persistence, replay ownership, batching, indexing, tenancy, and backpressure
   need separate storage and delivery decisions.

## Bounds and failure modes

- Existing path, authentication, response, and event-stream limits apply.
- The server enforces a maximum requested batch size of `1,000`; the stream's
  own capacity may be lower.
- A cursor before the retained ring returns `EVENT_CURSOR_EXPIRED` with HTTP
  `409`; consumers must explicitly recover from the reported retained window.
- Invalid query values return `EVENT_QUERY_INVALID` or
  `EVENT_CURSOR_INVALID` with HTTP `400`.
- An absent stream returns `EVENT_STREAM_UNAVAILABLE` with HTTP `503`, and a
  missing or wrong bearer token returns `UNAUTHORIZED` with HTTP `401`.
- The route performs no retry, queueing, durable persistence, batching,
  deduplication, fleet aggregation, remote search, tenancy, or exactly-once
  delivery claim.

## Consequences

Remote consumers can perform bounded cursor-based inspection of the same
redacted host-owned stream that receives event exports. Retention gaps remain
visible and cannot be mistaken for successful replay. Hosts that need durable
remote logs, aggregation, search, or stronger delivery guarantees still need a
separately reviewed transport and storage layer.
