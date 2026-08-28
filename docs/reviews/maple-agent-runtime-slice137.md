# MAPLE Agent Runtime Slice 137 Review

Date: 2026-08-27

Scope reviewed: bounded `DocumentCursorCheckpoint` state, in-memory/file
stores, `ingest_documents(...)` integration, exports, regressions, ADR-082,
API/README/parity documentation, and release-plan entry.

## Findings

- Checkpoints retain only a bounded opaque cursor, completion flag, and
  monotonic revision; document text, source metadata, credentials, prompts,
  and sink results are not persisted.
- File state is versioned, byte-bounded, atomically replaced, and serialized
  by the existing durable lease boundary. Stale or skipped revisions fail
  closed.
- Ingestion rejects two cursor authorities, loads state before connector
  activity, and never advances state before the current page is accepted by
  the sink. A completed checkpoint avoids a redundant connector call.
- The contract correctly remains at-least-once: a crash after sink success and
  before checkpoint save can redeliver a page. Exactly-once effects and
  idempotency remain host-owned.
- Focused/full regressions, whole-package typing, static/security scans, and
  dependency audit passed for the working tree.

## Disposition

Author-side review: no blocking finding for this slice. A fresh independent
verifier session was not available in this environment, so this record is not
represented as an independent verifier approval. Managed stores, connector
rate limits, retries, transactions, rollback, distributed scheduling, and
publication remain outside this slice.
