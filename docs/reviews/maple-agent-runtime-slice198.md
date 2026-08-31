# Slice 198 code review — bounded judge calibration

**Date:** 2026-08-29  
**Role:** Code Reviewer  
**Reviewed commits:** `35b446e`, `69df3fa`, `904f48a`, `bfe8b43`
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
  claim semantic/statistical validity. Valid existing `run` and `run_async`
  paths remain compatible; synchronous callbacks that return awaitables now
  fail closed and disposable coroutine-like values are closed.
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

## Follow-up review — synchronous judge awaitable cleanup

The follow-up commit `bfe8b43` closes the same public-boundary defect in both
`EvaluationHarness.calibrate(...)` and `EvaluationHarness.run(...)`. A
synchronous callback returning an awaitable is now reported as a bounded
`EVAL_JUDGE_RESULT_INVALID` case with an actionable async entry point, and a
disposable awaitable is closed before the per-case result is returned. No
provider, network, subprocess, dependency, or hosted persistence path was
introduced.

Evidence:

```text
python -m pytest tests/autonomy/test_evaluation.py -q --no-cov
37 passed in 0.31s
python -m ruff check maple/autonomy/evaluation.py tests/autonomy/test_evaluation.py
All checks passed!
python -m mypy --follow-imports=skip maple/autonomy/evaluation.py
Success: no issues found in 1 source file
python -m compileall -q maple/autonomy/evaluation.py tests/autonomy/test_evaluation.py
compileall: ok
python -m pytest -q --no-cov
1797 passed, 1 skipped in 357.31s (0:05:57)
```

Clean archive package smoke for the exact implementation commit `bfe8b43`:

```text
source_archive_entries=873
wheel_entries=108
sdist_entries=849
wheel_sha256=10ff1b4790f465066a590031c5ab1a7901d416ce1cfe4b36c18115e4ecd5ee90
sdist_sha256=35d99b05368f4ff0b640cad6bdcbc8a9ff950710a31f15011dc63a734f113ec5
build_exit=0
twine_exit=0
install_exit=0
import_ok 1.1.3 EvaluationHarness
doctor_network=false
doctor_ready=true
```

The full package mypy command remains affected by the repository's existing
missing/untyped optional dependency imports; it reported no changed-module
diagnostic. This remains author-context evidence and does not replace the
required fresh independent verifier session.
