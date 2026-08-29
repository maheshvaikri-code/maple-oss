# Slice 208 implementation plan - host-owned vector retrieval tool

**Class:** L
**Status:** Design accepted; implementation pending
**Brief:** `docs/briefs/maple-agent-runtime-slice208.md`
**ADR:** `docs/adr/152-bounded-vector-retrieval-tool.md`

## Gate plan

| Gate | Work | Evidence |
| --- | --- | --- |
| G0 | Confirm the vector RAG tool-loop gap, host-owned embedding scope, non-goals, and acceptance tests. | Slice brief committed before implementation. |
| G1 | Review the factory API, provider/backend delegation, shared citation shape, bounds, and error boundary. | ADR and this plan committed; Chief Architect role review. |
| G2 | Implement the adapter and public exports; add focused success, provider, backend, malformed-result, and disclosure regressions. | Focused retrieval/tool output and diff inspection. |
| G3 | Update API, README, parity, changelog, and release bookkeeping without widening provider or network claims. | Documentation smoke and diff inspection. |
| G4 | Run focused tests, full suite, static checks, and project-scoped security audit. | Pasted real command output in QA evidence. |
| G5 | Run a clean archived source/package smoke and file review/QA evidence. | Archive counts, build/Twine/install/import/doctor output. |
| G6 | Reconcile release readiness only; do not publish, tag, deploy, or update the website. | Conditional release decision and explicit remaining gates. |

## Implementation units

1. Add a private vector-to-retrieval-hit adapter in
   `maple/autonomy/retrieval.py` that invokes one caller-owned embedding
   provider and one vector backend search per bounded tool call.
2. Add `create_vector_retrieval_tool()` by reusing the existing validated
   retrieval citation serializer and its configuration constants.
3. Export the factory from `maple.autonomy` and the root `maple` package.
4. Add focused tests for valid vector citations, empty matched terms,
   provider/backend delegation and redaction, malformed provider/results,
   factory validation, query/top-k/output bounds, and no partial output.
5. Document the host-owned vector-query contract in API reference, README,
   parity ledger, changelog, and release plan.
6. Run the prescribed validation and clean archive smoke, then file review,
   QA/security, and release evidence.

## Safety and rollback checkpoints

- No new dependency, provider implementation, network, cloud, subprocess,
  execution, or website behavior.
- Do not alter the user's existing demo or doctrine files.
- Do not stage unrelated dirty or untracked files.
- If async provider support, provider routing, metadata passthrough, remote
  transport, authorization, or retry behavior is required, stop and open a
  separate contract.
- If provider/backend validation or shared serialization fails, return a typed
  generic error and never return a partial hit list.
