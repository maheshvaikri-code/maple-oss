# Slice 207 code review - bounded retrieval and citation tool

**Reviewer:** Code Reviewer role (in-session review)
**Candidate:** `1774551`
**Date:** 2026-08-29
**Independent verifier:** Unavailable in this environment; no fresh-session
review is claimed.

## Scope reviewed

- `maple/autonomy/retrieval.py`
- `maple/autonomy/__init__.py`
- `maple/__init__.py`
- `tests/autonomy/test_retrieval.py`
- Slice 207 brief, ADR, plan, API reference, README, parity ledger, changelog,
  and release-plan entries

## Verification performed

```text
python -m pytest tests/autonomy/test_retrieval.py --no-cov -q
============================= 51 passed in 1.07s ==============================

python -m black --check maple/autonomy/retrieval.py maple/autonomy/__init__.py maple/__init__.py tests/autonomy/test_retrieval.py
4 files would be left unchanged.

python -m ruff check maple/autonomy/retrieval.py maple/autonomy/__init__.py maple/__init__.py tests/autonomy/test_retrieval.py
All checks passed!

python -m mypy maple/ --ignore-missing-imports
Success: no issues found in 102 source files
```

## Findings

1. **[MINOR - resolved] Configured top-k default mismatch.** The first
   implementation used the global default inside the handler, which could
   reject an omitted `top_k` when `max_top_k` was configured below that value.
   The handler now derives the omitted value from the factory's configured
   bound. Covered by the focused query/top-k tests and committed in `7fa2d8a`.
2. **[MINOR - resolved] Huge numeric score conversion.** A backend could
   return an integer too large for `float()` and escape the intended malformed
   result error. Conversion is now caught and normalized to the generic
   result-invalid error; covered by the huge-score regression and committed in
   `7fa2d8a`.
3. **[MINOR - resolved] Boundary exception hardening.** Custom source/text or
   sequence values could raise during validation or sizing. Those paths now
   fail closed without raw exception details, and output size is checked after
   each serialized hit as well as for the final result. Committed in `1774551`.

## Review conclusion

- No open major or minor findings.
- The adapter is read-only, metadata-minimal, bounded, and does not interpret
  or execute retrieved text.
- Backend errors and malformed results do not expose raw backend messages,
  paths, or payloads.
- The first public factory is intentionally lexical-only; vector query
  embedding remains a separate contract.
- No new dependency, network call, subprocess, cloud action, HTTP route,
  execution-isolation behavior, or website change was introduced.

**Verdict:** PASS for the Slice 207 local contract, subject to the release
gates documented in the QA report and release checklist.
