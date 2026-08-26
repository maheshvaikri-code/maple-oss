# Slice 111 QA — Bounded Local Latency Percentiles

- Tested runtime tree: `247d37d`
- QA date: 2026-08-26
- Verdict: **PASS for behavior and local static gates**

## Functional evidence

Focused command:

```text
python -m pytest tests/autonomy/test_events.py tests/autonomy/test_observability.py tests/autonomy/test_runs.py -q --no-cov -p no:dash -p no:benchmark --tb=short --no-header
```

Observed result: `51 passed in 0.41s`.

Coverage includes deterministic span p50/p95/p99 values, empty samples,
bounded event sample capacity, existing event/span counters, retention,
sampling, exporter/subscriber isolation, and agent run compatibility.

Tracked application regression command:

```text
python -m pytest tests -q --no-cov -p no:dash -p no:benchmark --tb=short --no-header --ignore=tests/test_doctrine_gold.py --ignore=tests/test_doctrine_lint.py --ignore=tests/test_doctrine_metrics.py --ignore=tests/test_doctrine_packaging.py --ignore=tests/test_doctrine_state.py
```

Observed result: `1273 passed, 1 skipped in 255.46s (0:04:15)`.

The five ignored files are user-owned untracked Doctrine tests, not skipped
tracked application coverage.

## Static and runtime gates

- Changed-boundary mypy: `Success: no issues found in 2 source files`.
- Changed-source Ruff: `All checks passed!`.
- Black: all four changed Python files left unchanged after formatting.
- `compileall -q maple/autonomy tests/autonomy`: exit `0`.
- `git diff --check`: exit `0`.
- `python -m maple.cli doctor --json`: `ready: true`, all eight checks true,
  `network: false`.

## Release disposition

The bounded local observability behavior passes QA. A clean archive built from
committed candidate `0ac263b` produced wheel/sdist `1.1.3`; build exit was `0`,
both Twine checks were `PASSED`, the sdist contains `519` entries, all six
required public files are present, and the workspace-only audit found `0`
entries. The required package files are `README.md`, `LICENSE`,
`CHANGELOG.md`, ADR-057, this QA report, and the Slice 111 review report.
The dependency-governance gate remains open because the current shared
interpreter reports `383 known vulnerabilities in 77 packages`, and
`gitleaks`/`bandit` are unavailable in the environment.
