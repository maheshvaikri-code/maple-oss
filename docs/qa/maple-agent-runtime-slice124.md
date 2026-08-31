# MAPLE Agent Runtime Slice 124 QA Report

**Date:** 2026-08-27
**Scope:** provider-neutral bounded retrieval reranking
**Commit:** `aeb80bd`

## Acceptance evidence

| Criterion | Evidence | Pass |
|---|---|---|
| Host callback is explicit | `RetrievalReranker.score(query, chunk)` is supplied by the host; MAPLE does not select a model or make a network call. | Yes |
| Lexical and vector hits share one seam | `rerank_hits(...)` accepts both `RetrievalHit` and `VectorRetrievalHit` values and returns source-bearing `RerankedRetrievalHit` values. | Yes |
| Ranking is bounded and deterministic | Candidate count is capped at `100`, `top_k` is validated, scores must be finite, and ties use chunk ID ordering. | Yes |
| Original retrieval evidence is preserved | Each result retains `original_score`, the reranker score, the chunk, and its source reference. | Yes |
| Failure behavior is typed and redacted | Malformed candidates, invalid bounds, callback exceptions/errors, and malformed scores fail closed without provider exception text. | Yes |
| Existing behavior remains green | Focused retrieval suite: `12 passed in 0.07s`; full autonomy suite: `349 passed in 16.38s`; exact tracked manifest: `1311 passed, 1 skipped in 230.15s` across `108` tracked Python test files. | Yes |
| Public surface is exported and documented | Root/autonomy exports, README, API reference, parity ledger, changelog, ADR-070, and this QA/review evidence are updated. | Yes |

## Static and package evidence

- isort: changed import surfaces pass.
- Black: `4 files left unchanged` for the changed Python files.
- Ruff: `All checks passed!`.
- Changed-boundary mypy: `Success: no issues found in 1 source file`.
- Compile gate: passed for changed Python files.
- Diff check: passed; Git emitted only existing LF-to-CRLF normalization
  warnings for modified text files.
- Declared-project pip-audit: `No known vulnerabilities found`; no runtime
  dependency was added.
- Package build: `Successfully built maple_oss-1.1.3-py3-none-any.whl and
  maple_oss-1.1.3.tar.gz`; exit `0`.
- Twine: both wheel and sdist checks returned `PASSED`.
- Artifact shape: wheel `104` entries; sdist `565` entries.
- Candidate SHA-256: wheel
  `FEAF04DC6116609179E8E179CB2A0F99E47A6A819D0FA5408305AFA915E147E6`;
  sdist `684F78BF438A850D7837068DC4876013B2488AD08753090C03042218BE97C1B7`.
- Isolated wheel smoke: `wheel no-dependency retrieval rerank export smoke
  passed`.

## Security disposition

- The changed surface introduces no secret literal, executable deserialization,
  shell invocation, or new dangerous construct. `gitleaks` and `bandit` are
  unavailable in this environment.
- The environment-wide pip-audit is not a project-runtime result and remains a
  release veto: `384` known vulnerabilities across `77` installed packages.
  This must be dispositioned before publication.
- The reranker is a callback boundary only. It does not provide sandboxing,
  provider authentication, timeout/retry guarantees, or semantic-faithfulness
  evaluation.

## QA verdict

**Pass for Slice124 behavior and repository gates.** **Publication remains
blocked** by the environment-wide dependency-governance veto and still
requires the human-controlled release/publish decision. No publication,
deployment, cloud action, or website change was performed.
