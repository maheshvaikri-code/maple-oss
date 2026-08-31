# Slice 209 implementation plan - async host-owned vector retrieval tool

**Class:** L
**Status:** Complete locally; release-gated
**Brief:** `docs/briefs/maple-agent-runtime-slice209.md`
**ADR:** `docs/adr/153-async-vector-retrieval-tool.md`

## Gate plan

| Gate | Work | Evidence |
| --- | --- | --- |
| G0 | Confirm the async vector RAG tool-loop gap, host-owned provider scope, non-goals, and acceptance tests. | Slice brief committed before implementation. |
| G1 | Review the async-only API, executor boundary, shared citation shape, bounds, and cancellation/error policy. | ADR and this plan committed; Chief Architect role review. |
| G2 | Implement the protocol/factory and public exports; add focused async success, validation, redaction, no-sync-call, and no-partial-output regressions. | `82c8a24`; focused retrieval/tool output and diff inspection. |
| G3 | Update API, README, parity, changelog, and release bookkeeping without widening provider or network claims. | Public documentation and release-plan diff. |
| G4 | Run focused tests, full suite, static checks, and project-scoped security audit. | QA evidence: `73 passed`; full `1876 passed, 1 skipped`; static/audit pass. |
| G5 | Run a clean archived source/package smoke and file review/QA evidence. | QA evidence: source `980`, wheel `109`, sdist `894`; build/Twine/install/import/doctor pass. |
| G6 | Reconcile release readiness only; do not publish, tag, deploy, or update the website. | Review/QA filed; release remains conditional. |

## Implementation units

1. Add `AsyncEmbeddingProvider`, shared vector-result normalization, and an
   async-only vector retrieval factory in `maple/autonomy/retrieval.py`.
2. Reuse the existing bounded retrieval serializer and execute synchronous
   vector backend calls in the default executor.
3. Export the protocol and factory from `maple.autonomy` and `maple`.
4. Add focused async tests for delegation, pre-provider validation,
   async-required sync behavior, provider/backend redaction, malformed
   vectors/hits, output bounds, and metadata/vector omission.
5. Document the async host-owned provider contract in API reference, README,
   parity ledger, changelog, and release plan.
6. Run the prescribed validation and clean archive smoke, then file review,
   QA/security, and release evidence.

## Safety and rollback checkpoints

- No new dependency, provider implementation, network, cloud, subprocess,
  execution, or website behavior.
- Do not alter the user's existing demo or doctrine files.
- Do not stage unrelated dirty or untracked files.
- If async backend support, provider routing, retries, cancellation policy,
  metadata passthrough, remote transport, authorization, or managed storage
  is required, stop and open a separate contract.
- If provider/backend validation or shared serialization fails, return a typed
  generic error and never return a partial hit list.
