# Slice 209 code review - async host-owned vector retrieval tool

**Reviewer:** Code Reviewer role (in-session review)
**Candidate:** `96f4b46`
**Date:** 2026-08-29
**Independent verifier:** Unavailable in this environment; no fresh-session
review is claimed.

## Scope reviewed

- `maple/autonomy/retrieval.py`
- `maple/autonomy/__init__.py`
- `maple/__init__.py`
- `tests/autonomy/test_retrieval.py`
- Slice 209 brief, ADR, plan, API reference, README, parity ledger,
  changelog, and release-plan entry

## Verification performed

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

## Findings

1. The async factory validates model arguments and provider vectors before
   callbacks, awaits exactly one host provider call, and runs synchronous
   vector search in the default executor.
2. Async vector hits reuse the existing bounded citation serializer; direct
   sync execution fails explicitly and does not invoke host callbacks.
3. No open major or minor findings remain. The only unavailable checks are
   the fresh independent verifier, Bandit, and Gitleaks in this environment.

## Review conclusion

- The async provider contract is explicit, host-owned, and dependency-free.
- Query, vector, top-k, hit, score, source, JSON, output-size, and async-only
  boundaries fail closed without partial output or private error disclosure.
- No dependency, HTTP route, subprocess, cloud action, execution-isolation
  behavior, publication, or website change was introduced.

**Verdict:** PASS for the Slice 209 local contract, subject to the release
gates documented in the QA report and release checklist.
