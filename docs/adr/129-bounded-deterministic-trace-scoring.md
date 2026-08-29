# ADR-129: Bounded deterministic trace scoring

**Status:** Proposed  
**Date:** 2026-08-28  
**Decision owners:** Chief Architect / Backend / Observability / QA

## Context

MAPLE evaluates outputs, schemas, tool trajectories, retrieval coverage, and
lexical groundedness. It also records bounded local `TraceSpan` values, but no
evaluation contract can score their structural shape. The missing capability
is useful for regression fixtures, while a provider-owned judge or hosted trace
system would exceed this repository's local contract.

## Decision

Add `TraceEvalCase` and `EvaluationHarness.run_trace(...)` as a deterministic
local evaluation boundary. A fixture contains a bounded ordered tuple of
`TraceEvalSpan` values, each containing only a span name, status, and optional
parent index. A runner returns a bounded list or tuple of native `TraceSpan` or
identifier-free `TraceEvalSpan` values.

The native projection resolves parent span IDs to earlier sequence indexes and
discards trace IDs, span IDs, timestamps, and attributes. An unknown parent is
invalid rather than silently treated as a root. The score is the equally
weighted mean of three positional component scores: name equality, status
equality, and parent-index equality. Each component uses the larger of the
expected and actual sequence lengths as its denominator, so missing and extra
spans lower the score. A case passes only when there are no typed errors and
the score meets its bounded `min_score`.

Results reuse `EvalReport` and `EvalResult`, with a bounded summary in
`actual_output` and identifier-free `actual_trace` values. No span attributes,
prompts, tool arguments, results, provider data, remote state, or persistence
are added to the evaluation result.

## Alternatives considered

1. **Compare complete `TraceSpan.to_dict()` records.** Rejected because IDs and
   timestamps are runtime-generated and attributes can become an accidental
   sensitive-data channel.
2. **Add a model judge.** Rejected because provider selection, retries, and
   calibration need a separate host-owned contract.
3. **Store or search traces for evaluation.** Rejected because hosted and
   distributed trace lifecycle is explicitly outside this local slice.

## Consequences

Positive:

- trace structure becomes regression-testable and versionable;
- native runtime spans can be evaluated without exposing their identities;
- malformed and oversized trace input fails closed with bounded errors;
- existing evaluation APIs remain additive and compatible.

Negative:

- positional scoring does not establish semantic or causal correctness;
- parent indexes are sequence-local and cannot represent an evicted parent;
- hosts still own trace collection, retention, and any provider judge.

## Verification

The implementation must include fixture validation, native-span projection,
deterministic component-score tests, redaction/non-disclosure assertions,
limits, malformed-parent handling, runner failures, and below-threshold
behavior. Full release evidence is recorded in the slice plan and review/QA
artifacts after the clean archive gate.
