# QA Evidence - MAPLE Agent Runtime Slice 161

**Code tip tested:** `ae8855a`
**Date:** 2026-08-28
**Role:** QA Engineer

## Behavior gate

Focused delegation/tool command:

```text
python -m pytest --no-cov -q tests/autonomy/test_tools.py tests/autonomy/test_handoffs.py
```

Result: `49 passed in 0.30s`.

The focused tests cover exact sync/async token propagation to cancellation-aware
agent and handoff targets, cancelled durable handoff finalization, legacy target
compatibility, cancellation-aware tool handlers, and the rejected executor
configuration.

Full autonomy command:

```text
python -m pytest --no-cov -q tests/autonomy
```

Result: `490 passed in 20.47s`.

Final tracked manifest command:

```text
$testFiles = @(git ls-files 'tests/*.py' 'tests/**/*.py'); python -m pytest --no-cov -q $testFiles
```

Result: `1491 passed, 1 skipped in 221.72s (0:03:41)` from `1492` collected
tests.

## Static and security checks

- Changed-boundary mypy: passed with `Success: no issues found in 1 source
  file`.
- Changed-boundary Black, isort, Ruff, and compile: passed.
- Whole tracked Ruff and compile: passed.
- High-confidence credential-pattern scan: clean.
- Targeted dangerous-construct scan: clean.
- No dependency files changed in Slice161.
- Bandit: unavailable in the environment (`No module named bandit`).
- Environment-wide `pip_audit` remains a governance veto from the baseline:
  `384` known vulnerabilities across `77` installed packages; this slice adds
  no dependency.
- Repository-wide Black/isort/mypy retain documented baseline debt outside
  this slice; the changed boundary is clean.

## Package gate

The clean archive candidate at `0cb1622` passed the local package gate:

- `python -m build --wheel --sdist`: passed; produced
  `maple_oss-1.1.3-py3-none-any.whl` and `maple_oss-1.1.3.tar.gz`.
- `python -m twine check`: both artifacts `PASSED`.
- Isolated no-dependency wheel install and `import maple`: passed.
- Clean source archive: `758` entries; wheel: `104` entries; sdist: `672`
  entries with root `maple_oss-1.1.3`.
- `archive_untracked_entries=0` by construction from `git archive`; temporary
  gate artifacts were outside the repository.

The package gate was local-only. No publication, deployment, cloud action, or
website update is authorized or performed.

## QA disposition

Behavior, static, targeted security, and local package gates pass. Publication
still requires explicit human authorization and remains outside this task.
