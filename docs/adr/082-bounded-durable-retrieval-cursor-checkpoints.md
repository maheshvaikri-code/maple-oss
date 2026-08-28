# ADR-082: Bounded durable retrieval cursor checkpoints

Status: Accepted for preview

Date: 2026-08-27

## Context

MAPLE's document connector contract already bounds each page and returns an
opaque continuation cursor, but the host had to persist and rehydrate that
cursor outside the ingestion helper. A restart-safe local seam is useful for
long-running connector jobs, provided it does not imply a managed connector,
distributed queue, or exactly-once sink effect.

## Decision

Add `DocumentCursorCheckpoint` and the host-owned
`DocumentCursorCheckpointStore` protocol. `InMemoryDocumentCursorCheckpointStore`
supports thread-safe local tests and one-process jobs. The atomic
`FileDocumentCursorCheckpointStore` stores one bounded JSON record, uses the
existing durable lease boundary for cross-process writers, and replaces the
file only after a flushed temporary write.

The checkpoint contains only an optional bounded cursor, a completion flag,
and a monotonically increasing revision. Saves must use the next revision;
stale or skipped writers fail closed. `ingest_documents(...)` rejects an
explicit cursor when a checkpoint store is supplied, loads the checkpoint
before fetching, and advances it only after all documents in the page have
been accepted by the sink. A completed checkpoint returns an empty completed
report without calling the connector. `clear()` resets the position while
retaining the fencing revision.

The sink boundary remains at-least-once: a process can write a page and fail
before its checkpoint save, so a restart may deliver that page again. The
connector and sink own idempotency or deduplication policy.

## Alternatives considered

| Alternative | Decision |
| --- | --- |
| Persist cursors implicitly inside every connector | Rejected: connector lifecycle and storage ownership remain host-specific. |
| Add a managed database or remote checkpoint service | Deferred: it expands deployment, tenancy, credentials, and availability scope. |
| Save before sink writes | Rejected: a sink failure could permanently skip documents. |
| Claim exactly-once ingestion | Rejected: external sink effects cannot be atomically committed with this local checkpoint. |

## Security and failure boundaries

- Cursor payloads and checkpoint bytes are bounded; malformed, oversized, or
  version-invalid files fail closed before connector activity.
- File writes are atomic and serialized under the existing durable lease;
  revision fencing rejects stale writers.
- Checkpoints contain no document text, source metadata, credentials, prompts,
  or sink results.
- MAPLE performs no connector network calls, retries, transactions, rollback,
  managed-store selection, or remote scheduling.
