# Slice 207 implementation plan - bounded retrieval and citation tool

**Class:** L
**Status:** Design accepted; implementation in progress
**Brief:** `docs/briefs/maple-agent-runtime-slice207.md`
**ADR:** `docs/adr/151-bounded-retrieval-tool.md`

## Gate plan

| Gate | Work | Evidence |
| --- | --- | --- |
| G0 | Confirm the retrieval/RAG tool-loop gap, local-only scope, non-goals, and acceptance tests. | Slice brief committed before implementation. |
| G1 | Review the factory API, hit schema, byte limits, metadata policy, and error boundary. | ADR and this plan committed; Chief Architect role review. |
| G2 | Implement the adapter and public exports; add focused rejection and serialization tests. | Focused retrieval/tool output and diff inspection. |
| G3 | Update API, README, parity, changelog, and release bookkeeping without widening claims. | Documentation smoke and diff inspection. |
| G4 | Run focused tests, full suite, static checks, and project-scoped security audit. | Pasted real command output in QA evidence. |
| G5 | Run a clean archived source/package smoke and file review/QA evidence. | Archive counts, build/Twine/install/import/doctor output. |
| G6 | Reconcile release readiness only; do not publish, tag, deploy, or update the website. | Conditional release decision and explicit remaining gates. |

## Implementation units

1. Add bounded retrieval-tool constants and serialization helpers to
   `maple/autonomy/retrieval.py`.
2. Add `create_retrieval_tool()` over `RetrievalBackend`, with fail-closed
   backend/result validation and a metadata-minimal citation result.
3. Export the factory from `maple.autonomy` and the root `maple` package.
4. Add focused tests for configuration, valid citations, bounds, malformed
   hits, duplicate results, oversized output, backend errors, and disclosure
   behavior.
5. Document the model-facing lexical retrieval contract in API reference,
   README, parity ledger, changelog, and release plan.
6. Run the prescribed validation and clean archive smoke, then file review,
   QA/security, and release evidence.

## Safety and rollback checkpoints

- No new dependency, provider, network, cloud, subprocess, execution, or
  website behavior.
- Do not alter the user's existing demo or doctrine files.
- Do not stage unrelated dirty or untracked files.
- If vector query embedding, metadata passthrough, remote transport, or
  authorization policy must be added, stop and open a separate contract.
- If serialization or backend validation fails, return a typed generic error
  and never return a partial hit list.
