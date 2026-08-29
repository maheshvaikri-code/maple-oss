# ADR-155: Asynchronous document ingestion boundary

**Status:** Proposed - awaiting human approval for a new public contract
**Date:** 2026-08-29
**Deciders:** Chief Architect / Backend / Security / QA / Release; human approval required

## Context

MAPLE already provides bounded synchronous cursor ingestion, durable local
cursor checkpoints, a host-owned rate limiter, deterministic chunking, and
read-only local retrieval. Async connectors currently have no equivalent
runtime boundary, so hosts must duplicate safety and progress logic or block
an async agent loop while adapting a source. The design must preserve the
existing page-level at-least-once semantics and must not imply network,
managed-store, authorization, or exactly-once behavior.

## Proposed decision

We propose adding an `AsyncDocumentConnector` protocol with
`async fetch(cursor, *, limit) -> Result[DocumentBatch, Error]` and an
`async ingest_documents_async()` helper. The helper would reuse the existing
bounded batch, cursor, duplicate-ID, checkpoint, rate-limit, sink, and
redacted-error rules; await one connector page at a time; save a checkpoint
only after all documents in that page are accepted; and preserve the current
`ConnectorIngestReport` shape. To keep the event loop available, existing
synchronous host callbacks would run through the default executor. Normal
`asyncio` task cancellation would propagate at async boundaries; an effect
already started in a host sink would remain subject to the host's idempotency
policy. No provider, network, managed store, authorization, retry, or
exactly-once contract would be selected by MAPLE.

This proposal is not accepted for implementation until the human confirms the
new public surface and the executor/cancellation tradeoff.

## Alternatives considered

| Option | Pros | Cons | Why not |
| --- | --- | --- | --- |
| Async connector plus executor-backed existing host callbacks (proposed) | Smallest additive surface; reuses proven validation/checkpoint behavior; keeps the event loop responsive | A cancelled executor call cannot undo an already-started host effect; at-least-once/idempotency remains explicit | Recommended only if the human accepts the effect boundary |
| Require new async sink, checkpoint, and rate-limiter protocols | Strongest event-loop contract and cancellation visibility | Triples the public surface; duplicates host adapters; requires async implementations for existing local stores | Too broad for the first async ingestion slice |
| Run synchronous callbacks inline | Simplest implementation and no background effect after cancellation | A large document or file-backed sink can block the event loop | Violates the async runtime responsiveness requirement |
| Keep async ingestion outside MAPLE | No API or compatibility risk | Every host duplicates cursor safety, redaction, and checkpoint logic; parity gap remains | Does not solve the stated runtime problem |

## Data flow and failure posture

```text
async caller
    -> validate bounded options
    -> await connector.fetch(cursor, limit)
    -> validate DocumentBatch, cursor, and duplicate IDs
    -> execute each existing sync sink callback in bounded host executor
    -> execute checkpoint/rate-limit callbacks under the same explicit policy
    -> save next cursor only after the complete page succeeds
    -> return bounded ConnectorIngestReport
```

Fetch, validation, sink, and checkpoint errors fail closed with the existing
generic retrieval error families. A failed or cancelled page is not reported
as checkpointed. A sink effect that has already started is not rolled back by
MAPLE; hosts must use an idempotent sink when recovery may redeliver a page.

## Consequences

- Positive: async sources gain one canonical bounded ingestion path and do not
  need to duplicate cursor/checkpoint/error logic.
- Negative / debt accepted: executor-backed sync callbacks have cooperative
  rather than forceful cancellation, and page-level recovery remains
  at-least-once.
- Invalidation triggers: a required async index backend, transactional sink,
  remote ingestion API, exactly-once effect guarantee, or host policy/tenant
  boundary reopens this ADR as a separate contract.

## Rollback

If approved and later rolled back, remove the additive protocol, helper,
exports, tests, and documentation. Existing synchronous ingestion, indexes,
checkpoints, and source data remain unchanged; no deletion or migration is
required.
