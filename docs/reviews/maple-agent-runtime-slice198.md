# Slice 198 code review — bounded judge calibration

**Date:** 2026-08-29  
**Role:** Code Reviewer  
**Reviewed commits:** `35b446e`, `69df3fa`, `904f48a`  
**Design baseline:** `88119cb`  
**Status:** Pass with the documented local-verification limitation

## Scope

The review covers the additive evaluation contracts, public exports, sync and
async calibration methods, regression tests, and public documentation for
provider-neutral calibration against caller-supplied human labels.

## Findings

- No correctness, security, or compatibility blocker was found.
- Dataset validation completes before any judge callback is invoked; malformed
  labels, fixtures, observations, duplicate IDs, and case-limit violations
  return typed input errors.
- Callback observations are rebuilt from redacted, size-bounded output and
  trajectory values. Reports retain per-case outcomes and bounded rationale,
  never raw observations. Judge errors, exceptions, malformed results, and
  disagreements remain visible per case.
- Sync and async methods preserve input order and do not select providers,
  invoke models, retry callbacks, train/tune judges, persist hosted data, or
  claim semantic/statistical validity. Existing `run` and `run_async` paths are
  unchanged.
- The first API example used an exact floating-point `0.1` assertion; it was
  corrected to a tolerance assertion in `904f48a`, with a focused regression
  for oversized rationales and redacted trajectories.

## Evidence

```text
35 passed in 0.36s
All checks passed!
Success: no issues found in 3 source files
```

The focused command was:

```text
python -m pytest tests/autonomy/test_evaluation.py -q --no-cov
```

Changed-boundary static checks were:

```text
python -m ruff check maple/autonomy/evaluation.py maple/autonomy/__init__.py maple/__init__.py tests/autonomy/test_evaluation.py
All checks passed!
python -m mypy maple/autonomy/evaluation.py maple/autonomy/__init__.py maple/__init__.py --ignore-missing-imports
Success: no issues found in 3 source files
git diff --check 88119cb..HEAD -- <Slice 198 paths>
exit 0
```

This execution context cannot open the required fresh independent verifier
session, so this file is author-context review evidence and is not an
independent verifier sign-off.
