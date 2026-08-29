# Slice 211 implementation plan - asynchronous document ingestion

**Class:** L
**Status:** G0-G6 complete locally; publication remains human-gated
**Brief:** `docs/briefs/maple-agent-runtime-slice211.md`
**ADR:** `docs/adr/155-async-document-ingestion.md`

## Gate plan

| Gate | Work | Evidence |
| --- | --- | --- |
| G0 | Define the async retrieval parity problem, bounded acceptance criteria, non-goals, and contract questions. | Slice brief; human confirmed 2026-08-29. |
| G1 | Decide public protocol shape, executor ownership, cancellation, checkpoint, and at-least-once semantics. | ADR-155 accepted; human approved 2026-08-29. |
| G2 | Implement the approved design; preserve synchronous ingestion and add focused async regressions. | `maple/autonomy/retrieval.py`; `tests/autonomy/test_retrieval.py`; focused suite `95 passed in 9.19s`. |
| G3 | Export and document the additive contract; do not add providers, network clients, or hosted behavior. | `maple.autonomy`, `maple`, API/README/parity/changelog updates committed with the implementation. |
| G4 | Review event-loop blocking, cancellation, duplicate delivery, bounds, error disclosure, and unrelated diff scope. | `docs/reviews/maple-agent-runtime-slice211.md`; no findings. |
| G5 | Run focused/full tests, static checks, project audit, and clean archive smoke. | `docs/qa/maple-agent-runtime-slice211.md`; full/static/audit/package gates pass; unavailable security tools explicitly recorded. |
| G6 | Reconcile release readiness only; no version bump, tag, publication, cloud, or website action. | Release plan and `docs/releases/v1.1.4.md` updated; local release gates reconciled and publication gates remain closed. |

## Implemented slice scope

1. Add `AsyncDocumentConnector` and `ingest_documents_async()` with one-page
   async fetch, existing validation, executor-backed sync host callbacks,
   page-level checkpointing, and fail-closed errors.
2. Add async success, resume, completion, cancellation, rate-limit,
   malformed-page, stalled-cursor, duplicate-ID, sink/checkpoint failure,
   no-checkpoint-on-failure, and redaction regressions.
3. Export and document the public surface, parity status, and release scope.
4. Run review, QA/security, and clean package evidence.

## Threat sketch

Assets touched: source text, retrieval indexes, cursor checkpoints, and host
callback state. Entry points / untrusted inputs: async connector results,
cursor values, limits, document IDs/text/metadata, callback results, and task
cancellation. Worst plausible abuse: a hostile connector returns oversized,
duplicate, stalled, malformed, or private-error-bearing pages; a cancelled
executor effect is redelivered after restart; or a malicious source blocks
the event loop with an unbounded callback.

Controls: reuse current byte/count/identifier/document validation; validate a
page before adding it; persist only after a complete page; generic error
mapping; one page in flight; executor isolation for synchronous callbacks;
explicit at-least-once and idempotency documentation; no raw source/error
disclosure; and no network or execution behavior.

## Risks and rollback points

- Risk: executor cancellation cannot undo an active sink effect -> mitigation:
  page-level checkpoint after completion, explicit at-least-once contract,
  idempotent host sink requirement -> rollback: remove additive helper/protocol.
- Risk: duplicated logic diverges from synchronous ingestion -> mitigation:
  share validation/serialization helpers or keep behaviorally identical
  boundary tests -> rollback: return to host adapters until a shared core is
  designed.
## Approval gate closed

Human approval was received on 2026-08-29 for the additive public contract
and recommended executor/cancellation tradeoff. Implementation is complete
within the stated non-goals.

## Status snapshot

Done (with evidence): Slice 210 locally closed; Slice 211 implementation,
focused regressions, exports, public documentation, code review, QA/security,
and exact package smoke are complete. Next: release reconciliation only;
only human-gated release decisions remain. Blocked on: none within the
approved Slice 211 scope.

## Pre-implementation package revalidation

The current committed planning head `5aa067e20f953af0a1e0981e98304405ef72ffaf`
was smoke-tested without changing the implementation surface:

```text
source_archive_entries=990
wheel_entries=109
sdist_entries=904
build_exit=0
twine_exit=0
install_exit=0
import_exit=0
import_output=1.1.3
doctor_exit=0
doctor_output={"checks": {"core": true, "evaluation": true, "events": true, "execution": true, "interop": true, "retrieval": true, "server": true, "sessions": true}, "network": false, "ready": true, "status": "SUCCESS", "version": "1.1.3"}
```

This is package-health evidence only; it does not constitute approval or
implementation evidence for Slice 211.
