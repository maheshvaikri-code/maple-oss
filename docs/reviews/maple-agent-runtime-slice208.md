# Slice 208 code review - host-owned vector retrieval tool

**Reviewer:** Code Reviewer role (in-session review)
**Candidate:** `3d3f1a5`
**Date:** 2026-08-29
**Independent verifier:** Unavailable in this environment; no fresh-session
review is claimed.

## Scope reviewed

- `maple/autonomy/retrieval.py`
- `maple/autonomy/__init__.py`
- `maple/__init__.py`
- `tests/autonomy/test_retrieval.py`
- Slice 208 brief, ADR, plan, API reference, README, parity ledger,
  changelog, and release-plan entry

## Verification performed

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

## Findings

1. The adapter validates provider vectors before invoking a custom vector
   backend, rejects provider/backend errors generically, and performs no
   provider retry or network operation.
2. Vector hits are normalized into the existing bounded citation serializer;
   source/chunk metadata and embedding vectors do not cross the model tool
   boundary.
3. No open major or minor findings remain. The only unavailable checks are
   the fresh independent verifier, Bandit, and Gitleaks in this environment.

## Review conclusion

- The host-owned synchronous embedding contract is explicit and dependency-free.
- Query, vector, top-k, hit, score, source, JSON, and output-size boundaries
  fail closed without partial output or private error disclosure.
- The returned tool is read-only and approval-disabled by default, while the
  factory preserves an explicit approval option.
- No dependency, HTTP route, subprocess, cloud action, execution-isolation
  behavior, publication, or website change was introduced.

**Verdict:** PASS for the Slice 208 local contract, subject to the release
gates documented in the QA report and release checklist.
