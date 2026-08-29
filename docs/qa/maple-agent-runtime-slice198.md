# QA + Security Report — MAPLE agent runtime Slice 198

**QA Engineer** · **Security Reviewer** · **Date:** 2026-08-29  
**Build under test:** follow-up commit `bfe8b43`; earlier clean committed candidate
`a3d6e8a`; dirty workspace
verification includes preserved user-owned changes and untracked Doctrine tests.

## Acceptance criteria verification

| # | Criterion | Evidence | Pass |
|---|---|---|---|
| 1 | Bounded labeled fixtures produce deterministic agreement and optional score MAE | Focused evaluation suite: `35 passed in 0.36s`; covers per-case outcomes, agreement count/rate, scored cases, and mean absolute score error | yes |
| 2 | Sync and async judges preserve order without concurrency | Focused suite covers sequential async callbacks; implementation uses ordered loops and accepts sync or awaitable judges | yes |
| 3 | Disagreements and judge failures remain visible per case | Focused suite covers disagreement, returned error, malformed result, exception, and no-score behavior | yes |
| 4 | Observation/rationale boundary is redacted and bounded | Focused suite covers redacted trajectory arguments and oversized rationale rejection; no raw observation fields are stored in calibration results | yes |
| 5 | Empty and malformed datasets fail with typed bounded errors before callback invocation | Focused suite covers empty report, invalid label, case limit, and zero callback calls on invalid input | yes |
| 6 | Existing behavior, exports, static checks, and package smoke remain green | Dirty full suite, clean full suite, Ruff, mypy, compileall, build/Twine, isolated import, and offline doctor all pass below | yes |

## Regression evidence

Focused command:

```text
python -m pytest tests/autonomy/test_evaluation.py -q --no-cov
============================= 35 passed in 0.36s ==============================
```

Dirty workspace command:

```text
python -m pytest -q --no-cov
================= 1795 passed, 1 skipped in 361.26s (0:06:01) =================
```

Clean committed-HEAD archive command:

```text
source_archive_entries=928
python -m pytest -q --no-cov
================= 1678 passed, 1 skipped in 263.16s (0:04:23) =================
```

Static checks:

```text
python -m ruff check maple/ tests/
All checks passed!
python -m mypy maple/ --ignore-missing-imports
Success: no issues found in 101 source files
python -m compileall -q maple tests
exit 0
```

Clean package candidate `a3d6e8a`:

```text
python -m build --wheel --sdist
Successfully built maple_oss-1.1.3-py3-none-any.whl and maple_oss-1.1.3.tar.gz
python -m twine check dist\*
Checking dist\maple_oss-1.1.3-py3-none-any.whl: PASSED
Checking dist\maple_oss-1.1.3.tar.gz: PASSED
wheel_entries=108
sdist_entries=842
install_exit=0
import_ok
doctor_exit=0
doctor_network=false
doctor_ready=true
```

Package hashes:

```text
wheel_sha256=7a728557af0b36d2347ee788bdf307d8eb6d8cc64a6f0b72e8a25f4c435e16cd
sdist_sha256=f0212a48b42974174cb99cd8a7928c2b63a5b99b3a35d56060f2abe9ae6d5795
```

## Security sweep

- Declared-project dependency audit:

  ```text
  python -m pip_audit --progress-spinner off --strict .
  No known vulnerabilities found
  ```

- `gitleaks` and `bandit` are unavailable in this execution environment; no
  pass is claimed for either tool. A targeted changed-surface scan found only
  synthetic redaction examples such as `api_key: "secret"`; no credential or
  private-key material was introduced.
- The callback receives a rebuilt redacted/bounded `EvalObservation`; malformed
  datasets are rejected before callback invocation; result reports contain no
  raw observations. Provider selection, model calls, network access, retries,
  training, hosted persistence, and side effects are absent from this slice.
- No dependency, subprocess, dynamic evaluation, shell, authentication, or
  network path was added.
- Repository-wide `git diff --check` remains affected by a pre-existing
  trailing-space line in user-modified `demo_package/launch_demos.py`; the
  Slice 198 paths pass the scoped diff check.

**Security verdict:** sign-off for the scoped local Slice 198 boundary, with
the unavailable scanners recorded above. The standing shared-environment
vulnerability audit and fresh-verifier limitation remain release governance
items and are not waived here.

**QA verdict:** pass for Slice 198 local criteria. Publication remains blocked
by the existing release gates; no publication, cloud action, or website update
was performed.

## Follow-up QA/security verification — `bfe8b43`

The synchronous `run` and `calibrate` judge boundaries were exercised with
disposable awaitables. Both APIs close the value when possible, return a
bounded per-case `EVAL_JUDGE_RESULT_INVALID` error, preserve a missing judge
score, and direct callers to the corresponding async API. The regression
tests also prove the callback result is not accidentally executed.

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

Exact clean-archive package smoke for `bfe8b43`:

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

No dependency, network, subprocess, dynamic execution, authentication, or
external side effect was added. The package smoke and full-suite evidence
below remain the governing release evidence; publication is still not
authorized.
