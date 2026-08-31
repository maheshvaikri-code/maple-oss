# Slice 207 QA and security report - bounded retrieval and citation tool

**QA candidate:** `1774551`
**Date:** 2026-08-29
**Independent verifier:** Unavailable in this environment; the QA result is
based on the executed repository commands below.

## Acceptance matrix

| Criterion | Evidence | Result |
| --- | --- | --- |
| Factory configuration and public shape are bounded | `test_retrieval_tool_configuration_is_bounded`; export/import checks | PASS |
| Valid lexical hits become deterministic source citations | `test_retrieval_tool_returns_bounded_source_citations_without_metadata` | PASS |
| Invalid query/top-k and malformed hit paths fail closed | `test_retrieval_tool_rejects_invalid_queries_and_top_k`; malformed/duplicate/huge-score tests | PASS |
| Whole result output is bounded without truncation | `test_retrieval_tool_rejects_oversized_output_without_partial_hits`; incremental size checks | PASS |
| Backend failures are generic and redacted | `test_retrieval_tool_redacts_backend_failures` | PASS |
| Public docs and exports match the implementation | README, API reference, parity ledger, changelog, release plan, root and autonomy exports | PASS |
| Repository verification is green | Focused/full/static/audit/package evidence below | PASS |

## Executed verification

```text
python -m pytest tests/autonomy/test_retrieval.py --no-cov -q
============================= 51 passed in 1.07s ==============================

python -m pytest -q
================= 1854 passed, 1 skipped in 398.14s (0:06:38) =================

python -m black --check maple/autonomy/retrieval.py maple/autonomy/__init__.py maple/__init__.py tests/autonomy/test_retrieval.py
4 files would be left unchanged.

python -m ruff check maple/autonomy/retrieval.py maple/autonomy/__init__.py maple/__init__.py tests/autonomy/test_retrieval.py
All checks passed!

python -m mypy maple/ --ignore-missing-imports
Success: no issues found in 102 source files

python -m compileall -q maple tests
exit 0

python -m pip_audit --strict .
No known vulnerabilities found
```

The full suite collected `1855` tests and skipped the existing optional NATS
test. The project audit emitted only the environment-location warning before
the clean result.

## Clean archive/package smoke

The smoke used `git archive HEAD` into an isolated temporary checkout and did
not include preserved untracked workspace files:

```text
archive_exit=0
extract_exit=0
source_archive_entries=970
wheel_entries=109
sdist_entries=884
sdist_test_entries=137
wheel_excluded_entries=0
sdist_excluded_entries=0
build_exit=0
twine_exit=0
venv_exit=0
install_exit=0
import_exit=0
import_output=1.1.3 create_retrieval_tool
doctor_exit=0
doctor_output={"checks": {"core": true, "evaluation": true, "events": true, "execution": true, "interop": true, "retrieval": true, "server": true, "sessions": true}, "network": false, "ready": true, "status": "SUCCESS", "version": "1.1.3"}
```

The sdist intentionally contains `tests/` because `MANIFEST.in` explicitly
includes tests for development installs. The excluded-scope check is for the
separately maintained `demo_package/` and `n8n-integration/` trees.

## Security checks and limits

- Token-shaped custom scan over `af9fd4d..HEAD`: `token_matches=0`.
- Gitleaks: unavailable in the environment; no Gitleaks pass is claimed.
- Bandit: unavailable in the environment; no Bandit pass is claimed.
- `pip_audit --strict .`: clean for the declared MAPLE project.
- No dependency manifest changed in this slice.
- The new adapter performs no SQL, shell, subprocess, network, import,
  `eval`, or execution operation. It returns retrieved content as data only.
- Query UTF-8 bytes, top-k, hit count, identifiers, score finiteness, matched
  terms, source validity, JSON serialization, and complete output bytes are
  bounded. Source/chunk metadata is omitted from model-visible results.
- Backend exceptions, malformed `Result` values, malformed hits, duplicate
  chunks, and output overflow fail closed with generic typed errors.

The worktree hygiene check reports only pre-existing trailing whitespace in
the preserved user-owned `demo_package/launch_demos.py`; no user file was
modified, staged, or normalized by this slice.

## QA/security disposition

**QA:** PASS for the local Slice 207 acceptance contract.

**Security:** PASS with the explicitly recorded Gitleaks, Bandit, and fresh
independent-verifier availability limitations. Existing CI/header, hosted,
execution-isolation, cloud, publication, and website gates remain separate.
