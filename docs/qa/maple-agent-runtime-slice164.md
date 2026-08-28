# QA Evidence - MAPLE Agent Runtime Slice 164

**Code tip tested:** `fbbb4b0`
**Date:** 2026-08-28
**Role:** QA Engineer

## Behavior gate

Focused command:

```text
python -m pytest tests/autonomy/test_handoffs.py tests/autonomy/test_tools.py tests/autonomy/test_runs.py -q
```

Result: `106 passed in 4.34s`.

The focused tests cover explicit bounded child-run IDs, sync and async native
start/resume contracts, in-flight child recovery after `RUN_EXISTS`, invalid
identities, cancellation forwarding, bounded result handling, and preservation
of legacy delegation behavior.

Full autonomy command:

```text
python -m pytest tests/autonomy -q
```

Result: `503 passed in 26.00s`.

Final tracked manifest command:

```text
$testFiles = @(git ls-files -- 'tests/*.py' 'tests/**/*.py'); python -m pytest @testFiles -q
```

Result: `1504 passed, 1 skipped in 234.44s (0:03:54)` from `1505` collected
tests.

## Static and security checks

- Changed-boundary Black, isort, Ruff, compile, and mypy passed.
- Whole tracked Ruff and compile passed.
- High-confidence secret-marker scan passed.
- Targeted dangerous-construct scan passed.
- No dependency files changed in Slice164.
- Bandit is unavailable in the environment (`No module named bandit`).
- The environment-wide `python -m pip_audit --local` run exited `1` after a
  cache/network JSON decode failure; the established environment baseline is
  `384` known vulnerabilities across `77` packages. This slice adds no
  dependency.

## Package gate

The clean file-backed `git archive` candidate at `fbbb4b0` passed the local
package gate:

- `python -m build --sdist --wheel --no-isolation`: passed with build exit `0`.
- Produced `maple_oss-1.1.3-py3-none-any.whl` and
  `maple_oss-1.1.3.tar.gz`.
- Source archive: `769` entries.
- Wheel archive: `104` entries.
- Source distribution: `683` entries with root `maple_oss-1.1.3`.
- `python -m twine check`: both artifacts `PASSED`.
- Isolated no-dependency wheel install and `import maple`: passed.
- The archive was constructed from `git archive`, so untracked workspace files
  were excluded by construction.

The package gate was local-only. No publication, deployment, cloud action, or
website update is authorized or performed.

## QA disposition

Behavior, static, targeted security, and local package gates pass for Slice164.
Bandit and the environment-wide pip-audit run remain environment limitations,
not Slice164 dependency or behavior failures. Existing user-owned workspace
changes remain preserved outside this slice.
