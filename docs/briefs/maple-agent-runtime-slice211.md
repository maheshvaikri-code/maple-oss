# Slice 211 brief - asynchronous document ingestion

**Date:** 2026-08-29
**Class:** L (new public async connector and ingestion contract)
**Requested by:** human MAPLE parity/release objective

## Problem

MAPLE's retrieval layer can ingest bounded cursor pages from synchronous
connectors, but an async source must currently be adapted outside the public
runtime. That forces hosts to duplicate cursor, limit, duplicate-ID,
checkpoint, rate-limit, and error-boundary logic, or to block an agent event
loop while bridging the source. The gap is visible in the retrieval parity
ledger and is independent of any particular provider or managed store.

## Scope

- In: one public `AsyncDocumentConnector` protocol; one public
  `ingest_documents_async()` helper; the existing bounded `DocumentBatch`,
  `DocumentIngestor`, checkpoint, and rate-limiter contracts; async cursor
  paging; page-level at-least-once checkpoint semantics; cancellation at
  async boundaries; focused regressions; public documentation; and release
  evidence.
- **Non-goals:** network clients, provider selection, retries, batching or
  prefetch beyond one page, managed stores, corpus authorization, distributed
  coordination, exactly-once effects, rollback of an already-started sink
  write, or a new async vector/index backend.
- Deferred: async sink/checkpoint/rate-limiter protocols, remote ingestion
  transport, provider-specific connector adapters, and policy-aware corpus
  access.

## Acceptance criteria (numbered, testable)

1. Given a valid async connector and bounded host-owned sink, when a caller
   awaits `ingest_documents_async()`, then it fetches at most one bounded
   page at a time, adds each validated document, and returns the same
   `ConnectorIngestReport` shape and cursor semantics as synchronous
   ingestion.
2. Given a checkpoint store, when a page is fully added, then the next cursor
   is saved exactly once after the page's sink operations; when fetch,
   validation, sink, rate-limit, or checkpoint work fails, then no checkpoint
   for the incomplete page is saved.
3. Given an invalid batch size, document/batch limit, cursor, connector
   result, stalled cursor, empty advancing page, or repeated document ID,
   when ingestion is called, then it returns the corresponding bounded typed
   retrieval error before the next unsafe operation and does not add the
   invalid page.
4. Given a connector, sink, checkpoint store, or rate limiter that raises or
   returns a malformed/private error, when ingestion runs, then the result is
   a generic fail-closed error without exception text, source payloads, or
   partial page reporting.
5. Given a completed checkpoint or a caller cancellation at an async
   boundary, when ingestion runs, then completed state is not refetched,
   cancellation propagates, and no new checkpoint is written for an
   incomplete page. Any already-started host sink effect remains governed by
   the host's at-least-once/idempotency policy.
6. The new protocol and helper are importable from `maple.autonomy` and
   `maple`; public docs state bounds, errors, ownership, cancellation, and
   at-least-once semantics; no network, hosted, exactly-once, or execution
   capability claim is added.
7. Focused async retrieval regressions, the full suite, static gates,
   project-scoped dependency audit, and clean package smoke pass.

## Constraints

- Python >=3.8; zero new dependencies; preserve synchronous ingestion and
  all existing public signatures.
- Connector fetch is the only required async callback in this slice. Existing
  synchronous host callbacks must have an explicit event-loop blocking and
  cancellation policy before implementation is approved.
- Every caller-influenced count, cursor, document, error, and serialized
  checkpoint remains bounded. Checkpointed sink progress is at-least-once,
  not exactly-once.
- No website, cloud, registry, tag, or publication action.

## Assumptions (chosen defaults - correct me if wrong)

- The recommended first contract is async connector plus existing sync sink,
  checkpoint, and rate limiter, with synchronous host callbacks isolated from
  the event loop by the default executor.
- The helper uses normal `asyncio` task cancellation only; it does not add a
  new `CancellationToken` parameter in this slice.
- Page-level checkpointing remains compatible with `ingest_documents()` and
  deliberately preserves its at-least-once recovery semantics.

## Open questions (blocking - answered before G1)

1. Approve the new public `AsyncDocumentConnector` and
   `ingest_documents_async()` contract for implementation?
2. Confirm the recommended executor boundary for existing synchronous sink,
   checkpoint, and rate-limiter callbacks, accepting that cancellation cannot
   undo a host effect that has already started; alternatively, require new
   async counterparts before this slice proceeds.

**Human confirmed:** no - explicit approval is required under Doctrine §5.
