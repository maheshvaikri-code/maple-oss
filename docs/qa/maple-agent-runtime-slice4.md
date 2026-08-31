# QA + Security Report - MAPLE Agent Runtime Slice 4 @ 953f601

**QA Engineer:** local verification role  · **Security Reviewer:** local
security pass  · **Date:** 2026-08-24
**Build under test:** `953f601 feat(autonomy): add retrieval data primitives`

## Acceptance criteria

| # | Criterion | Evidence | Pass |
|---|---|---|---|
| 1 | Documents and source references are typed. | `Document`, `SourceRef`, `DocumentChunk`, and `RetrievalHit` are public and tested. | Yes |
| 2 | Chunking is deterministic and bounded. | Character offsets, overlap, max document bytes, and max chunks are tested. | Yes |
| 3 | Retrieval returns grounded hits. | Ranked lexical hits retain source URI, chunk text, offsets, and matched terms. | Yes |
| 4 | Empty, malformed, duplicate, oversized, and removal paths are covered. | Retrieval regression suite covers all listed cases. | Yes |
| 5 | Existing autonomy behavior remains green. | `120 passed, 1 warning`. | Yes |

## Security sweep

- No new dependency was added.
- The tokenizer is a fixed `\w+` expression; it is not schema- or user-supplied
  and is applied only after bounded document/query checks.
- Metadata is JSON-serialized for validation and size accounting; no executable
  deserialization, eval, exec, pickle, subprocess, shell, or YAML-loader path
  was added.
- Source URIs and identifiers are bounded and control-character checked.
- The in-memory backend is explicitly documented as a local reference backend,
  not a hosted or multi-tenant isolation boundary.

## Regression evidence

```text
20 passed, 1 warning in 0.08s
120 passed, 1 warning in 0.20s
```

The broader repository run remains unfinished evidence: the previous run
reached `1008 passed` before interruption in an existing slow timing path. It
is not treated as a full-suite release pass.

## Verdict

**Security:** SIGN-OFF for the dependency-free Slice 4 reference backend;
final release security sign-off remains open.
**QA:** pass for Slice 4; final release QA remains open pending the remaining
slices and a completed repository regression run.
