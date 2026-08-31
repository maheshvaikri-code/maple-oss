# ADR-142: Bounded provider-neutral judge calibration

**Date:** 2026-08-29
**Status:** accepted for the scoped local preview contract
**Deciders:** Chief Architect

## Context

MAPLE's evaluation harness already accepts host-supplied synchronous or
asynchronous judges and redacts observations before judge exposure. It has no
first-class calibration dataset or aggregate agreement metric, leaving hosts
to implement this safety check outside the bounded evaluation contract. The
ML engineering standard requires calibration against human labels before
judge scores are treated as evidence.

## Decision

We will add `EvalCalibrationCase`, per-case `EvalCalibrationResult`, and
aggregate `EvalCalibrationReport` values plus synchronous and asynchronous
`EvaluationHarness.calibrate(...)` methods. Calibration will reuse the
existing case/observation validation, redaction, size bounds, judge-result
normalization, and sequential callback semantics; it will report binary
agreement and optional score mean absolute error without selecting a provider,
calling a model, training a judge, or claiming statistical or semantic
validity.

## Alternatives considered

| Option | Pros | Cons | Why not |
|---|---|---|---|
| Bounded local calibration contract (chosen) | Deterministic, dependency-free, redaction-preserving, directly measures agreement before use | Depends on the quality and representativeness of caller-supplied human labels | Best fit for the existing host-owned judge seam and local release gates |
| Provider/model-owned calibration service | Could automate judge execution and model-specific policy | Requires provider choice, credentials, network, privacy policy, quotas, and a model-version contract | Human-gated external boundary; not suitable for this local slice |
| Host computes ad hoc metrics / do nothing | No code change | Repeats unsafe/unbounded logic and leaves calibration absent from reports | Fails the reusable evaluation-contract requirement |

## Data flow and failure boundary

```text
human-labeled EvalCalibrationCase
          |
          v
case + observation validation -- malformed dataset --> typed input error
          |
          v
redaction + size bounds
          |
          v
host-supplied sync/async judge -- exception/invalid result --> per-case error
          |
          v
bounded per-case result -- disagreement --> agreed=False
          |
          v
agreement + optional score-error aggregate / JSON report
```

## Consequences

- Positive: hosts receive a reusable, bounded calibration report and can see
  judge disagreement before relying on judge scores; existing judge callbacks
  and provider-neutral evaluation remain unchanged.
- Negative / debt accepted: descriptive agreement and mean absolute error do
  not prove semantic quality, statistical confidence, label quality, or live
  provider compatibility; calibration data remains caller-owned.
- Invalidation triggers: provider-owned judge selection, automatic training or
  threshold tuning, confidence intervals, hosted persistence, human-label
  workflows, or cross-run calibration aggregation would require a new scope,
  privacy review, and explicit external contract.
