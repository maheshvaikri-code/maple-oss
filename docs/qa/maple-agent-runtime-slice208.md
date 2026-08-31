# Slice 208 QA and security report - host-owned vector retrieval tool

**QA candidate:** `3d3f1a5`
**Date:** 2026-08-29
**Independent verifier:** Unavailable in this environment; the QA result is
based on the executed repository commands below.

## Acceptance matrix

| Criterion | Evidence | Result |
| --- | --- | --- |
| Host embedding and vector search compose through one tool call | `test_vector_retrieval_tool_delegates_host_embedding_and_returns_citations`; provider call count and vector-tool schema assertions | PASS |
| Vector citations use the shared bounded result shape | Valid citation test; empty `matched_terms`; metadata and embedding omission assertions | PASS |
| Provider vectors, provider/backend failures, malformed hits, duplicates, and scores fail closed | Invalid-vector parameterization; provider/backend redaction tests; shared result-validation regressions | PASS |
| Output remains bounded without partial hits | `test_vector_retrieval_tool_rejects_oversized_output_without_partial_hits` | PASS |
| Public exports and documentation match the implementation | Root/autonomy exports; README, API reference, parity ledger, changelog, ADR, brief, plan, and release bookkeeping | PASS |
| Repository verification is green | Focused/full/static/audit/package evidence below | PASS |

## Executed verification

```text
python -m pytest tests/autonomy/test_retrieval.py --no-cov -q
============================= 64 passed in 1.05s ==============================

python -m pytest --no-cov -q
================= 1867 passed, 1 skipped in 391.40s (0:06:31) =================

python -m black --check maple/autonomy/retrieval.py maple/autonomy/__init__.py maple/__init__.py tests/autonomy/test_retrieval.py
4 files would be left unchanged.

python -m ruff check maple/autonomy/retrieval.py maple/autonomy/__init__.py maple/__init__.py tests/autonomy/test_retrieval.py
All checks passed!

python -m mypy --ignore-missing-imports maple
Success: no issues found in 102 source files

python -m compileall -q maple
exit 0

python -m pip_audit --strict .
No known vulnerabilities found
```

The full suite collected `1868` tests and skipped the existing optional NATS
test. The project audit emitted only the environment-location warning before
the clean result. A bare `python -m mypy maple` also reports the established
unrelated missing optional dependency/stub errors in NATS, Streamstore,
CrewAI, AutoGen, psutil, msgpack, and protobuf; the repository's established
release check uses `--ignore-missing-imports` and passed above.

## Clean archive/package smoke

The smoke used `git archive HEAD` at committed candidate `3d3f1a5` in an
isolated temporary checkout and did not include preserved untracked workspace
files:

```text
archive_exit=0
extract_exit=0
source_archive_entries=975
wheel_entries=109
sdist_entries=889
sdist_test_entries=137
wheel_excluded_entries=0
sdist_excluded_entries=0
build_exit=0
twine_exit=0
venv_exit=0
install_exit=0
import_exit=0
import_output=1.1.3 create_vector_retrieval_tool
doctor_exit=0
doctor_output={"checks": {"core": true, "evaluation": true, "events": true, "execution": true, "interop": true, "retrieval": true, "server": true, "sessions": true}, "network": false, "ready": true, "status": "SUCCESS", "version": "1.1.3"}
```

The sdist intentionally contains `tests/` because `MANIFEST.in` explicitly
includes tests for development installs. The excluded-scope check is for the
separately maintained `demo_package/` and `n8n-integration/` trees.

## Security checks and limits

- Token-shaped custom scan over `d1e28af..HEAD`: `token_matches=0`.
- Gitleaks: unavailable in the environment; no Gitleaks pass is claimed.
- Bandit: unavailable in the environment; no Bandit pass is claimed.
- `pip_audit --strict .`: clean for the declared MAPLE project.
- No dependency manifest changed in this slice.
- The adapter performs no SQL, shell, subprocess, network, import, `eval`, or
  execution operation. It returns retrieved content as data only.
- Provider query vectors are bounded for dimensions, finiteness, and non-zero
  content before backend delegation. Query UTF-8 bytes, top-k, hit count,
  identifiers, score finiteness, source validity, JSON serialization, and
  complete output bytes are bounded.
- Backend/provider exceptions, malformed `Result` values, malformed hits,
  duplicate chunks, and output overflow fail closed with generic typed errors.

The committed-diff hygiene check is clean. The broader worktree still reports
only pre-existing trailing whitespace in the preserved user-owned
`demo_package/launch_demos.py`; no user file was staged or normalized.

## QA/security disposition

**QA:** PASS for the local Slice 208 acceptance contract.

**Security:** PASS with the explicitly recorded Gitleaks, Bandit, and fresh
independent-verifier availability limitations. Existing CI/header, hosted,
execution-isolation, cloud, publication, and website gates remain separate.
