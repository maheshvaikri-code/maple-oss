# Slice 209 QA and security report - async host-owned vector retrieval tool

**QA candidate:** `96f4b46`
**Date:** 2026-08-29
**Independent verifier:** Unavailable in this environment; the QA result is
based on the executed repository commands below.

## Acceptance matrix

| Criterion | Evidence | Result |
| --- | --- | --- |
| Async provider and vector search compose through the async tool loop | `test_async_vector_retrieval_tool_delegates_without_blocking_event_loop`; provider call count and executor-thread assertions | PASS |
| Async tool is explicit and validates before callbacks | `test_async_vector_retrieval_tool_is_async_only_and_validates_before_provider`; sync-required and invalid-query/top-k assertions | PASS |
| Async vector citations use the shared bounded result shape | Async success and oversized-output tests; empty matched terms and embedding omission assertions | PASS |
| Provider/backend failures, invalid vectors, malformed results, and output overflow fail closed | Provider/backend redaction parameterizations, invalid-vector test, and shared result-validation regressions | PASS |
| Public exports and documentation match the implementation | Root/autonomy exports; README, API reference, parity ledger, changelog, ADR, brief, plan, and release bookkeeping | PASS |
| Repository verification is green | Focused/full/static/audit/package evidence below | PASS |

## Executed verification

```text
python -m pytest tests/autonomy/test_retrieval.py --no-cov -q
============================= 73 passed in 1.14s ==============================

python -m pytest --no-cov -q
================= 1876 passed, 1 skipped in 400.38s (0:06:40) =================

python -m black --check maple/autonomy/retrieval.py maple/autonomy/__init__.py maple/__init__.py tests/autonomy/test_retrieval.py
4 files would be left unchanged.

python -m ruff check maple/autonomy/retrieval.py maple/autonomy/__init__.py maple/__init__.py tests/autonomy/test_retrieval.py
All checks passed!

python -m mypy --ignore-missing-imports maple
Success: no issues found in 102 source files

python -m compileall -q maple tests
exit 0

python -m pip_audit --strict .
No known vulnerabilities found
```

The full suite collected `1877` tests and skipped the existing optional NATS
test. The project audit emitted only the environment-location warning before
the clean result. A bare `python -m mypy maple` continues to report the
established unrelated missing optional dependency/stub errors; the
repository's established release check uses `--ignore-missing-imports` and
passed above.

## Clean archive/package smoke

The smoke used `git archive HEAD` at committed candidate `96f4b46` in an
isolated temporary checkout and did not include preserved untracked workspace
files:

```text
archive_exit=0
extract_exit=0
source_archive_entries=980
wheel_entries=109
sdist_entries=894
sdist_test_entries=137
wheel_excluded_entries=0
sdist_excluded_entries=0
build_exit=0
twine_exit=0
venv_exit=0
install_exit=0
import_exit=0
import_output=1.1.3 AsyncEmbeddingProvider create_async_vector_retrieval_tool
doctor_exit=0
doctor_output={"checks": {"core": true, "evaluation": true, "events": true, "execution": true, "interop": true, "retrieval": true, "server": true, "sessions": true}, "network": false, "ready": true, "status": "SUCCESS", "version": "1.1.3"}
```

The sdist intentionally contains `tests/` because `MANIFEST.in` explicitly
includes tests for development installs. The excluded-scope check is for the
separately maintained `demo_package/` and `n8n-integration/` trees.

## Security checks and limits

- Token-shaped custom scan over `82c8a24..HEAD`: `token_matches=0`.
- Gitleaks: unavailable in the environment; no Gitleaks pass is claimed.
- Bandit: unavailable in the environment; no Bandit pass is claimed.
- `pip_audit --strict .`: clean for the declared MAPLE project.
- No dependency manifest changed in this slice.
- The adapter performs no SQL, shell, subprocess, network, import, `eval`, or
  execution operation. It returns retrieved content as data only.
- Provider vectors are bounded for dimensions, finiteness, and non-zero
  content before executor-backed backend delegation. Query UTF-8 bytes,
  top-k, hit count, identifiers, score finiteness, source validity, JSON
  serialization, and complete output bytes are bounded.
- Provider/backend exceptions, malformed `Result` values, malformed hits,
  duplicate chunks, and output overflow fail closed with generic typed errors.
- Cancellation of a provider that ignores cancellation and external effects
  remain host-owned; MAPLE does not claim exactly-once behavior.

The committed-diff hygiene check is clean. The broader worktree still reports
only pre-existing trailing whitespace in the preserved user-owned
`demo_package/launch_demos.py`; no user file was staged or normalized.

## QA/security disposition

**QA:** PASS for the local Slice 209 acceptance contract.

**Security:** PASS with the explicitly recorded Gitleaks, Bandit, and fresh
independent-verifier availability limitations. Existing CI/header, hosted,
execution-isolation, cloud, publication, and website gates remain separate.
