# QA Evidence - MAPLE Agent Runtime Slice 162

**Code tip tested:** `6982878`
**Date:** 2026-08-28
**Role:** QA Engineer

## Behavior gate

Focused command:

```text
python -m pytest --no-cov -q tests/autonomy/test_runs.py tests/autonomy/test_handoffs.py tests/autonomy/test_tools.py
```

Result: `96 passed in 0.52s`.

The focused tests cover sync and async successful-result replay for
`create_agent_tool`, parent-journal lookup/save behavior, regenerated
tool-call-ID rebinding, existing durable-run replay, cancellation propagation,
handoff behavior, and tool validation.

Full autonomy command:

```text
python -m pytest --no-cov -q tests/autonomy
```

Result: `492 passed in 20.44s`.

Final tracked manifest command:

```text
$testFiles = @(git ls-files 'tests/*.py' 'tests/**/*.py'); python -m pytest --no-cov -q $testFiles
```

Result: `1493 passed, 1 skipped in 223.64s (0:03:43)` from `1494` collected
tests.

## Static and security checks

- Changed-boundary mypy: passed with `Success: no issues found in 1 source
  file`.
- Changed-boundary Black, isort, Ruff, and compile: passed.
- Whole tracked Ruff and compile: passed.
- High-confidence credential-pattern scan: clean.
- Targeted dangerous-construct scan: clean.
- No dependency files changed in Slice162.
- Bandit: unavailable in the environment (`No module named bandit`).
- Environment-wide `pip_audit` remains a governance veto from the baseline:
  `384` known vulnerabilities across `77` packages; this slice adds no
  dependency.
- Repository-wide Black/isort/mypy retain documented baseline debt outside
  this slice; the changed boundary is clean.

## Package gate

Pending on the release-candidate documentation commit. No publication,
deployment, cloud action, or website update is authorized or performed.

## QA disposition

Behavior, static, and targeted security gates pass. The package gate must run
from the final committed release tip before publication can be considered.
