# Slice 206 implementation plan - durable local vector retrieval

**Class:** L  
**Status:** In progress  
**Brief:** `docs/briefs/maple-agent-runtime-slice206.md`  
**ADR:** `docs/adr/150-file-vector-retriever.md`

## Gate plan

| Gate | Work | Evidence |
| --- | --- | --- |
| G0 | Confirm local vector durability gap, scope, non-goals, and acceptance tests. | Slice brief committed before implementation. |
| G1 | Review the public shape, persistence envelope, limits, lease ownership, and error boundary. | ADR and this plan committed; Chief Architect role review. |
| G2 | Implement the bounded file backend by reusing `InMemoryVectorRetriever`; add focused regressions and public exports. | Focused retrieval test output, diff, static checks. |
| G3 | Update API, README, parity, changelog, and release bookkeeping; keep claims local-only. | Documentation smoke and diff inspection. |
| G4 | Run focused tests, full suite, static checks, and project-scoped security audit. | Pasted real command output in QA evidence. |
| G5 | Run a clean archived source/package smoke and file release/review evidence. | Archive entry counts, build/Twine/install/import/doctor output. |
| G6 | Evaluate release boundary only; do not publish, tag, deploy, or update the website. | Conditional release decision and explicit remaining gates. |

## Implementation units

1. Add versioned vector-index constants and serialization helpers to
   `maple/autonomy/retrieval.py`.
2. Add `FileVectorRetriever` with constructor validation, bounded reads,
   candidate rebuilds, atomic durable writes, local fencing, and typed
   redacted errors.
3. Export the class from `maple.autonomy` and the root `maple` package.
4. Add focused tests for configuration, persistence/reload, corruption,
   policy/dimension mismatch, failed writes, concurrency, refresh/bounds, and
   error redaction.
5. Document the exact local-only caller-supplied-embedding contract in the
   API reference, README, parity record, and changelog.
6. Run the prescribed validation and archive smoke, then file review/QA and
   release-plan evidence.

## Safety and rollback checkpoints

- No new dependency, provider, network call, cloud call, or website change.
- Do not alter the user's existing demo or doctrine files.
- Do not stage unrelated dirty or untracked files.
- If the format or public contract must expand beyond this brief, stop for
  human approval before implementation.
- If a write fails, preserve the prior file and candidate state; tests must
  prove this property.

