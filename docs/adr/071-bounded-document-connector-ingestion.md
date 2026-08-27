# ADR-071: Bounded Document Connector and Ingestion Contract

## Status

Accepted - preview capability, local-first.

## Context

MAPLE has dependency-free lexical and caller-supplied-vector retrieval, but
hosts still need a stable boundary for loading documents from files, APIs, or
managed stores. The source and store vary by deployment, so retrieval should
not select a loader, open a network connection, or own a provider client.

## Decision

Add a host-owned cursor connector contract and bounded ingestion helper:

- `DocumentConnector.fetch(cursor, limit=...)` returns one `DocumentBatch`;
- each batch contains validated source-bearing `Document` values and an
  optional opaque continuation cursor;
- `ingest_documents(...)` feeds pages into an explicit `DocumentIngestor`,
  including the existing lexical retriever or a host adapter;
- a batch is capped at `100` documents, one ingestion call at `10,000`
  documents and `100` fetched batches, and each requested page is capped at
  `100` items;
- document IDs must be unique within a batch and across one ingestion call;
  advancing cursors must be non-empty and cannot stall;
- the result reports bounded progress, the next cursor, and whether the
  connector is complete;
- connector and sink exceptions or error results are converted to typed,
  redacted errors, with no implicit retry or network operation.

## Alternatives considered

1. **Add file, HTTP, or managed-store loaders to MAPLE.** Rejected because
   credentials, networking, pagination, rate limits, and provider lifecycle
   belong to the host deployment.
2. **Expose an unbounded document iterator.** Rejected because a connector
   could exhaust memory or run forever without a cursor, page, or quota.
3. **Make each retriever own connector ingestion.** Rejected because vector
   stores and external indexes have different write contracts and would make
   loading implicit.
4. **Add a transaction or automatic rollback around the sink.** Rejected
   because arbitrary sinks cannot promise rollback; partial sink progress is
   reported as a host-owned operational policy.

## Bounds and failure modes

- `batch_size` is between `1` and `100`; `max_documents` is between `1` and
  `10,000`; and `max_batches` is between `1` and `100`.
- Empty pages may terminate a connector but may not advance its cursor.
- A repeated document ID, invalid document, malformed cursor, or stalled
  cursor fails closed before that page is sent to the sink.
- Connector failures return `RETRIEVAL_CONNECTOR_ERROR`; sink failures return
  `RETRIEVAL_SINK_ERROR`; callback messages and exception text are not exposed.
- There is no retry, timeout, network call, deduplication persistence,
  transaction, rollback, or exactly-once ingestion guarantee.

## Consequences

Hosts can connect local files, APIs, or managed retrieval stores to MAPLE's
existing document and source-reference contract without adding runtime
dependencies. Cursor progress and quotas make ingestion resumable and bounded,
while the explicit sink keeps storage ownership outside the core. Managed
store adapters, rate-limit policy, durable cursor checkpoints, and semantic
quality evaluation remain separate follow-on decisions.
