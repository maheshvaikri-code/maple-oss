# Slice 131 QA — Bounded structured evaluation trajectories @ `3194c1e`

**QA Engineer** · **Security Reviewer** · **Date:** 2026-08-27
**Build under test:** `3194c1e` (`feat/evaluation: add structured trajectories`)

## Acceptance criteria verification

| # | Criterion | How executed | Evidence (real output) | Pass |
|---|---|---|---|---|
| 1 | Structured fixtures can assert bounded tool arguments, results, status, and duration | New exact trajectory fixture and report assertions | `24 passed in 0.26s`; exact structured step matching passed and name-only observations remained compatible | PASS |
| 2 | Actual trajectories are redacted before report and judge exposure | Secret-bearing report and judge tests | `44 passed in 0.40s`; both report and judge saw `[REDACTED]` for the token-bearing argument/result | PASS |
| 3 | Invalid, inconsistent, and oversized trajectory data fails closed per case | Invalid status/duration, name mismatch, per-step, and total report-bound tests | `24 passed in 0.26s`; malformed contracts returned typed case/observation errors without aborting the harness | PASS |
| 4 | Existing evaluation semantics and public compatibility remain intact | Exact tracked manifest, exports, API/README/parity review | `1348 passed, 1 skipped in 274.74s`; existing two-argument `EvalObservation` tests passed | PASS |
| 5 | Release boundary remains dependency-free and tracked-source-only | Clean archive build, Twine check, entry counts, and isolated `python -S` smoke | `build_exit=0`; wheel `104` entries; sdist `579` entries; Twine checks `PASSED`; no-dependency structured-trajectory export smoke passed | PASS |

## Adversarial & edge matrix

| Input/scenario | Expected | Observed | Pass |
|---|---|---|---|
| Exact structured trajectory | Expected arguments/results/status/duration match | Fixture passed with a redacted report copy | PASS |
| Name-only observation | Existing callers remain valid | Existing trajectory tests and full manifest passed | PASS |
| Name/step mismatch | Reject observation | `EVAL_OBSERVATION_INVALID` | PASS |
| Invalid fixture step | Reject case before runner | `EVAL_TRAJECTORY_STEP_INVALID` / `EVAL_CASE_INVALID` | PASS |
| Per-step oversized values | Reject structured step | Typed trajectory-step error | PASS |
| Total redacted report over limit | Do not expose unbounded report/judge data | `EVAL_OBSERVATION_INVALID` | PASS |
| Secret-bearing arguments/results | Redact before report and judge | `[REDACTED]` observed in both destinations | PASS |

## Regression

Focused evaluation suite:

```text
24 passed in 0.26s
```

Evaluation plus observability suite:

```text
44 passed in 0.40s
```

Exact tracked manifest:

```text
tracked_test_files=108
1348 passed, 1 skipped in 274.74s (0:04:34)
```

Static and security gates:

```text
4 files would be left unchanged.                 # Black --check
All checks passed!                                # Ruff
Success: no issues found in 1 source file         # mypy evaluation.py --follow-imports=skip
secret_scan: no high-confidence credential patterns in Slice 131 diff
dangerous_construct_scan: no new eval/exec/pickle/unsafe-yaml/shell/disabled-TLS patterns in Slice 131 diff
No known vulnerabilities found                    # pip_audit . --skip-editable
```

No runtime dependency was added. The project-scoped audit is clean; the
environment-wide audit still reports `384` known vulnerabilities across `77`
installed packages and remains a release-governance veto outside this slice.

## Bugs found

| # | Repro steps (minimal) | Severity | Fixed @ | Re-verified | Regression test |
|---|---|---|---|---|---|
| — | — | — | — | No Slice 131 defects found | Structured matching, compatibility, validation, redaction, judge propagation, and bound tests above |

## Security sweep

The evaluator accepts only host-supplied `EvalTrajectoryStep` values. It does
not execute arguments, results, or generated code. Each step validates tool
identity, allowed status, finite bounded duration, and JSON-safe bounded
arguments/results. Reports and judges receive a separately re-redacted copy,
and the whole trajectory is bounded by `max_value_bytes`.

The Slice 131 diff had no high-confidence credential patterns and no new
dangerous construct patterns. `python -m pip_audit . --skip-editable` reported
`No known vulnerabilities found`; no runtime dependency was added. The
environment-wide dependency finding above is a governance veto, not a defect
introduced by this slice.

**Security verdict:** SIGN-OFF · human override: n/a
**QA verdict:** pass
