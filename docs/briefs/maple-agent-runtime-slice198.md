# Slice 198 brief - bounded judge calibration

**Date:** 2026-08-29
**Class:** L (new public evaluation contracts and aggregate reporting)
**Requested by:** human continuation request

## Problem

MAPLE can run a host-supplied generation-quality judge, but it cannot measure
whether that judge agrees with human-labeled examples before the judge is used
for release or regression decisions. Without a bounded calibration report,
hosts must compute agreement ad hoc and may mistake an uncalibrated judge score
for evidence of quality.

## Scope

- In: bounded human-labeled calibration cases, redacted observations,
  provider-neutral sync and async judge callbacks, per-case calibration
  results, binary agreement rate, optional score mean absolute error, and JSON
  report serialization.
- **Non-goals:** model/provider invocation or selection, judge training,
  automatic threshold tuning, confidence intervals, statistical significance,
  hosted evaluation, durable calibration storage, or distributed execution.
- Deferred: provider-owned judge orchestration, provider-specific calibration
  policies, rubric version registries, and human-label management workflows.

## Acceptance criteria

1. Given bounded labeled fixtures and a synchronous judge, when
   `EvaluationHarness.calibrate(...)` runs them sequentially, then it returns
   deterministic per-case judge outcomes plus total cases, agreement count,
   agreement rate, scored-case count, and optional mean absolute score error.
2. Given the same fixtures and a synchronous or awaitable judge, when
   `EvaluationHarness.calibrate_async(...)` runs, then it preserves fixture
   order and produces the same metrics without concurrent callbacks.
3. Given a judge disagreement, when calibration completes, then the case is
   recorded as `agreed=False` without being hidden or converted into a harness
   exception; given a judge error, exception, or malformed result, then the
   case records a typed error and no judge score is reported for that case.
4. Given a calibration observation containing redaction-key data, oversized
   values, invalid trajectories, or oversized rationale, when the judge is
   called or the report is serialized, then only the existing bounded,
   redacted observation/rationale crosses the judge/report boundary.
5. Given zero cases, when calibration runs, then it returns an empty report
   with agreement rate `0.0` and no score-error aggregate; given more than the
   configured case limit or malformed labels/fixtures, then it returns a
   typed input error without invoking the judge.
6. The feature adds no dependency or network call, preserves existing
   `EvaluationHarness.run`/`run_async` behavior, exports the public types, and
   passes focused and full repository tests.

## Constraints

- Reuse the existing `EvalCase`, `EvalObservation`, `EvalJudgeResult`,
  redaction, size bounds, and `Result` error contract.
- Process cases sequentially and retain no raw observations in reports.
- Human labels are inputs, not claims that the judge is semantically correct.
- Preserve existing user-owned changes outside this slice.

## Assumptions (chosen defaults - correct me if wrong)

- `expected_passed` is the binary human label used for agreement; an optional
  `expected_score` enables score-error measurement and is not required for
  binary calibration.
- Invalid dataset fixtures are caller/input errors returned before callback
  invocation; judge failures are per-case report errors so the remaining
  calibration set is still observable.
- Agreement and mean absolute error are descriptive bounded metrics, not
  confidence intervals or a deployment approval decision.

## Open questions (blocking - answered before G1)

- None for this local provider-neutral contract. Provider-owned judge and
  hosted calibration decisions remain separate human-gated work.

**Human confirmed:** yes - standing continuation request on 2026-08-29
