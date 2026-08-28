# QA Evidence - MAPLE Agent Runtime Slice 160

**Code tip tested:** `ed82f76`  
**Date:** 2026-08-28  
**Role:** QA Engineer

## Behavior gate

Command:

```text
python -m pytest --no-cov tests/autonomy/test_execution.py tests/autonomy/test_tools.py tests/autonomy/test_agent.py tests/autonomy/test_runs.py -q
```

Result: `128 passed in 0.82s`.

The focused tests cover pre-cancelled sync/async goals, invalid token values,
durable sync/async terminal cancellation, metadata-only cancellation events,
non-mutating paused interaction cancellation, tool-level cancellation, and
trusted-executor propagation.

Final tracked manifest command:

```text
$testFiles = @(git ls-files 'tests/*.py' 'tests/**/*.py'); python -m pytest --no-cov -q $testFiles
```

Result: `1482 passed, 1 skipped in 228.90s (0:03:48)`.

## Static and security checks

- Changed-boundary mypy: passed with `Success: no issues found in 3 source files`.
- Changed-boundary Black, isort, Ruff, and compile: passed.
- Whole tracked Ruff and compile checks: passed.
- Targeted secret and dangerous-construct scans: clean.
- Bandit: unavailable in the environment (`No module named bandit`).
- Environment-wide `pip_audit` remains a governance veto from the baseline:
  `384` known vulnerabilities across `77` installed packages; this slice adds
  no dependency.
- Repository-wide Black/isort/mypy still have documented baseline debt outside
  this slice; changed boundaries are clean.

## QA disposition

Behavior and static gates pass. Package evidence is recorded after the final
documentation closure commit; no publication, deployment, cloud action, or
website update is authorized or performed.
