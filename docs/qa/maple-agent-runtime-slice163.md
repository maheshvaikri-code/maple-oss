# QA Evidence - MAPLE Agent Runtime Slice 163

**Code tip tested:** `ad16afc`
**Date:** 2026-08-28
**Role:** QA Engineer

## Behavior gate

Focused command:

```text
python -m pytest tests/autonomy/test_handoffs.py tests/autonomy/test_server.py -q
```

Result: `56 passed in 19.04s`.

The focused tests cover bounded and defensively copied results, legacy records,
file-store restart persistence, sync and async explicit-ID replay, task/result
identity checks, failed/cancelled/result-less non-replay, malformed results,
and authenticated remote result redaction.

Full autonomy command:

```text
python -m pytest tests/autonomy -q
```

Result: `500 passed in 25.80s`.

Final tracked manifest command:

```text
$testFiles = @(git ls-files -- 'tests/*.py' 'tests/**/*.py'); python -m pytest @testFiles -q
```

Result: `1501 passed, 1 skipped in 228.61s (0:03:48)` from `1502` collected
tests.

## Static and security checks

- Changed-boundary mypy with `--follow-imports=skip`: passed with
  `Success: no issues found in 3 source files`.
- Changed-boundary Black, isort, Ruff, and compile: passed.
- Whole tracked Ruff and compile: passed.
- High-confidence secret-marker scan: passed.
- Targeted dangerous-construct scan: passed.
- No dependency files changed in Slice163.
- Bandit: unavailable in the environment (`No module named bandit`).
- Environment-wide `pip_audit --local` is not clean and exits `1` because the
  environment contains packages not found on PyPI, including `rudradb-trishul`,
  `spheredb`, `threadwork`, `torch`, `torchaudio`, `torchvision`, `umap`, and
  `zizu`; this slice adds no dependency.
- Repository-wide Black/isort/mypy retain documented baseline debt outside this
  slice; the changed boundary is clean.

## Package gate

The clean git-archive candidate at `ad16afc` passed the local package gate:

- `python -m build --wheel --sdist`: passed with build exit `0`; produced
  `maple_oss-1.1.3-py3-none-any.whl` and `maple_oss-1.1.3.tar.gz`.
- `python -m twine check`: both artifacts `PASSED`.
- Clean source archive: `764` entries.
- Wheel archive: `104` entries.
- Source distribution: `678` entries with root `maple_oss-1.1.3`.
- Isolated no-dependency wheel install and `import maple`: passed.
- The archive was constructed from `git archive`, so untracked workspace files
  were excluded by construction.

The package gate was local-only. No publication, deployment, cloud action, or
website update is authorized or performed.

## QA disposition

Behavior, static, targeted security, and local package gates pass. Publication
still requires explicit human authorization and remains outside this task.
