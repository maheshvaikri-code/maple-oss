# ADR-048: Versioned evaluation fixtures and optional judge contract

**Date:** 2026-08-26  
**Status:** accepted  
**Deciders:** Chief Architect, Backend, Security, QA

## Context

MAPLE's evaluation harness already provides deterministic exact-output,
schema, trajectory, retrieval, and lexical groundedness checks. The general
agent-framework comparison set also makes two useful evaluation practices
visible: versioned golden trajectories and an optional model-judge path.

Without a fixture version, a stored trajectory case has no explicit contract
revision in its report. Without a judge boundary, hosts must add an ad-hoc
callback around the harness and can accidentally turn provider failures or
unbounded rationale text into release decisions.

## Decision

`EvalCase.fixture_version` is an additive integer field bounded to versions
1 through 32 and defaults to 1. Ordered tool expectations are bounded to 256
names of at most 256 control-free characters. The version is copied into each
`EvalResult` and JSON-compatible report entry.

`EvaluationHarness.run` accepts an optional host-supplied `EvalJudge`. The
callback receives the validated case and a redacted, size-bounded
`EvalObservation`. It returns `EvalJudgeResult` directly or through MAPLE's
`Result` type. A valid judge result contains a finite score from 0 to 1, an
explicit boolean decision, and bounded text rationale. The judge is an
additional report check; deterministic checks remain unchanged.

Judge errors, exceptions, malformed results, invalid scores, and invalid
rationales fail the individual case with typed errors. MAPLE does not select
or invoke a provider, retry a judge, calibrate a score, execute arbitrary
generated code, or claim semantic faithfulness. Hosts own provider selection,
prompt/rubric design, privacy review, and repeatability policy.

## Alternatives considered

| Option | Pros | Cons | Why not |
|---|---|---|---|
| Add bounded version and optional local judge (chosen) | Small additive contract; deterministic baseline remains usable; provider-neutral | Does not provide calibration or async execution | Appropriate boundary for a dependency-free runtime |
| Make every evaluation model-judged | Broader semantic coverage | Non-deterministic, provider-dependent, costly, and harder to reproduce | Violates MAPLE's local deterministic baseline |
| Accept an untyped judge mapping | Flexible integration | Ambiguous pass semantics and weak bounds | Typed result is safer for release gates |

## Consequences

- Golden trajectory fixtures can report which bounded contract version they
  were evaluated against.
- Hosts can layer a calibrated judge over deterministic checks without MAPLE
  taking ownership of model credentials or provider availability.
- A judge is synchronous and local in this release slice; async provider
  orchestration, batching, calibration, trace scoring, and hosted evaluation
  remain separate contracts.
