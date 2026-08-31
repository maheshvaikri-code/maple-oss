# QA + Security Report - durable local vector retrieval @ 926e872

**QA Engineer** · **Security Reviewer** · **Date:** 2026-08-29
**Build under test:** exact committed runtime candidate `926e872`; the later
evidence-only documentation commit does not change runtime code.

## Acceptance criteria verification

| # | Criterion | How executed | Evidence (real output) | Pass |
|---|-----------|--------------|------------------------|------|
| 1 | Bounded configuration and fail-closed corrupt/oversized/incompatible state | Focused vector tests cover invalid limits, invalid UTF-8, corrupt JSON, oversized bytes, unsupported and boolean versions, malformed vectors, and chunking-policy mismatch. | `python -m pytest tests/autonomy/test_retrieval.py --no-cov -q` -> `43 passed in 1.05s` | yes |
| 2 | Atomic persistence and restart search of caller-supplied vectors | Add a document, inspect the versioned envelope, construct a second retriever, and query the same source. | Focused suite -> `43 passed in 1.05s`; package import smoke -> `1.1.3 FileVectorRetriever` | yes |
| 3 | Count/dimension/duplicate rejection and fail-closed remove | Focused tests assert no file mutation for count, dimension, duplicate, huge-component, and failed-remove writes; successful remove persists. | Focused suite -> `43 passed in 1.05s` | yes |
| 4 | Shared-directory mutation serialization | Two retrievers add documents concurrently and a fresh instance verifies both records. | Focused suite -> `43 passed in 1.05s` | yes |
| 5 | Refresh, deterministic hits, and query/result bounds | A second instance observes an external add; invalid `top_k` and non-finite query values fail. | Focused suite -> `43 passed in 1.05s` | yes |
| 6 | Redacted JSON/vector/storage failures | Non-JSON metadata, malformed persisted vectors, non-finite/overflow values, and a private writer exception are exercised; raw exception text is asserted absent. | Focused suite -> `43 passed in 1.05s`; no private failure text observed in returned error | yes |
| 7 | Regression, static, audit, and clean package readiness | Full suite, formatter/linter/type/compile checks, project audit, and clean `git archive HEAD` package smoke. | Full suite -> `1846 passed, 1 skipped in 398.27s (0:06:38)`; mypy -> `Success: no issues found in 102 source files`; pip-audit -> `No known vulnerabilities found`; package smoke below | yes |

## Adversarial & edge matrix

| Input/scenario | Expected | Observed | Pass |
|----------------|----------|----------|------|
| Missing vector state file | Empty index, no partial state | Second-instance construction before the first add succeeds; refresh test passes | yes |
| Oversized state (`513` bytes with `max_bytes=512`) | Constructor rejects before exposure | `ValueError("vector index state is invalid")` in focused test | yes |
| Corrupt JSON and invalid UTF-8 | Fail closed | Constructor rejection covered; focused suite green | yes |
| Boolean/unsupported schema version | Fail closed | Constructor rejection covered; focused suite green | yes |
| Malformed/non-finite/overflow vector | Structured invalid-vector or state error, no raw exception | Focused suite covers bad strings, NaN, and `10**10000`; 43 passed | yes |
| Zero/negative limits and invalid lease/chunker | Constructor rejects | Configuration test covers zero, below-minimum bytes, NaN lease, and wrong chunker | yes |
| Duplicate document | No mutation, typed duplicate error | Focused assertion returns `RETRIEVAL_DUPLICATE_DOCUMENT`; file bytes unchanged | yes |
| Concurrent writers | Both completed peer updates survive | Two retrievers add concurrently; fresh stats report two documents/two vectors | yes |
| Unicode/JSON metadata | Valid JSON-safe values persist; unsupported values reject | Shared `Document`/JSON contract and full retrieval suite pass; no new encoding path bypasses validation | yes |
| Failed/interrupted candidate write | Prior durable state remains authoritative | Failed remove preserves bytes/searchability; atomic temp-file cleanup path is covered by implementation and existing lease/file tests | yes |
| Limit-1/limit/limit+1 result queries | In-range succeeds; out-of-range rejects | `top_k=2` succeeds with `max_results=2`; `top_k=3` returns `RETRIEVAL_QUERY_INVALID` | yes |

## Regression

```text
python -m pytest -q
================= 1846 passed, 1 skipped in 398.27s (0:06:38) =================

python -m black --check maple/autonomy/retrieval.py maple/autonomy/__init__.py maple/__init__.py tests/autonomy/test_retrieval.py
4 files would be left unchanged.

python -m ruff check maple/autonomy/retrieval.py maple/autonomy/__init__.py maple/__init__.py tests/autonomy/test_retrieval.py
All checks passed!

python -m mypy maple/ --ignore-missing-imports
Success: no issues found in 102 source files

python -m compileall -q maple tests
(exit 0)

python -m pip_audit --strict .
No known vulnerabilities found
```

Flakes: none observed.

## Bugs found

| # | Repro steps (minimal) | Severity | Fixed @ | Re-verified | Regression test |
|---|----------------------|----------|---------|-------------|-----------------|
| 1 | Submit `10**10000` as one vector component. | MAJOR | `5366c09` | Focused and full suites green | `test_file_vector_retriever_rejects_vector_dimension_mismatch_without_mutation` |
| 2 | Persist JSON with `{"version": true}`. | MINOR | `926e872` | Focused and full suites green | `test_file_vector_retriever_rejects_corrupt_oversized_or_mismatched_state` |
| 3 | Review found missing direct duplicate/malformed-vector assertions. | MINOR | `484eae0` | Focused and full suites green | persistence/rejection tests in `tests/autonomy/test_retrieval.py` |

## Security sweep

- Secrets scan: a token-shaped scan over `git diff cf7002a..HEAD` returned no
  matches. Gitleaks is unavailable in this tool context (`gitleaks=unavailable`),
  so no Gitleaks pass is claimed.
- Injection review: no SQL, shell construction, template rendering, or
  network input was added. The caller-selected directory is converted to a
  `Path`; the persisted filenames are fixed; JSON is parsed with a bounded
  binary read; output is produced through `json.dumps(..., allow_nan=False)`.
- Deserialization: JSON only; no `pickle`, `eval`, or `exec` is used. Stored
  documents and vectors are revalidated before rebuilding the index.
- Dependencies: no dependency manifest changed in the slice. `python -m
  pip_audit --strict .` exited `0` with `No known vulnerabilities found`.
- Dangerous constructs: writes use `tempfile.NamedTemporaryFile`, flush,
  `os.fsync`, and `os.replace`; no subprocess, disabled TLS, unsafe code, or
  world-writable file behavior was added. Bandit is unavailable (`No module
  named bandit`), so no Bandit pass is claimed.
- Bounds/fail-closed: bounded file reads, document/vector/dimension/result
  limits, finite numeric validation, fixed schema/policy checks, durable
  fencing, atomic replacement, and generic redacted errors are covered.

**Security verdict:** SIGN-OFF with the tooling limitations above recorded; no
human override.
**QA verdict:** pass.
