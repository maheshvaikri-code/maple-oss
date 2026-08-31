# Code Review — bounded code-block artifact materialization @ 3382595

**Reviewer role:** Code Reviewer · **Date:** 2026-08-29
**Reviewed against:** [Slice 195 brief](../briefs/maple-agent-runtime-slice195.md) · [Slice 195 plan](../plans/maple-agent-runtime-slice195.md) · [ADR-139](../adr/139-bounded-code-block-artifact-materialization.md)

**Executed:**

```text
python -m pytest -q --no-cov tests/autonomy/test_artifacts.py tests/autonomy/test_contracts.py
============================= 25 passed in 0.44s ==============================

python -m pytest -q --no-cov
================= 1765 passed, 1 skipped in 337.57s (0:05:37) =================

python -m black --check maple/autonomy/artifacts.py maple/autonomy/__init__.py maple/__init__.py tests/autonomy/test_artifacts.py
4 files would be left unchanged.

python -m isort --check-only maple/autonomy/artifacts.py maple/autonomy/__init__.py maple/__init__.py tests/autonomy/test_artifacts.py
exit code 0

python -m ruff check maple/autonomy/artifacts.py maple/autonomy/__init__.py maple/__init__.py tests/autonomy/test_artifacts.py
All checks passed!

python -m mypy maple/ --ignore-missing-imports
Success: no issues found in 101 source files

python tools/doctrine_lint.py
doctrine_lint: corpus clean

git diff --cached --check
exit code 0
```

## Findings

| # | Sev | Location | Finding | Suggested fix | Resolution |
|---|-----|----------|---------|---------------|------------|
| 1 | [MAJOR] | `tests/autonomy/test_artifacts.py` | The first review pass found that the acceptance criterion for a public import/runnable example and the store-exception path lacked direct tests. | Add a top-level public API round-trip test and a deterministic exception-raising store test. | Fixed before `3382595`; focused suite rerun at 25 passed and full suite rerun at 1765 passed. |

No open BLOCKERs, MAJORs, MINORs, or NITs remain.

## Scope check

The diff matches the plan: it adds the `CodeBlock.sha256` view, one bounded
materialization helper over the existing `ArtifactStore.put` boundary, public
exports, regression tests, README/API/parity/changelog documentation, and the
Slice 195 design/release records. It does not add execution, compilation,
subprocesses, sandboxing, browser/computer use, network fetches, hosted stores,
new dependencies, cloud work, publication, or website changes.

Correctness checks covered exact UTF-8 bytes and SHA-256 identity, deterministic
safe names, the 128 KiB helper cap, in-memory and restartable file stores,
invalid inputs, path-like names, store quota failures, a raising store, and
code containing a file-writing expression remaining inert. The helper delegates
quota, persistence, and hash verification to the existing stores and returns
their typed results.

## Verdict

- [x] Pass (0 BLOCKER, MAJORs resolved)
- [ ] Return to build — findings above

This is a local review pass. A fresh independent verifier session could not be
launched in the current execution context, so this report does not claim
independent verifier approval.
