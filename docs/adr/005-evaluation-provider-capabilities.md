# ADR-005: Local evaluation and declared provider capabilities

**Status:** Accepted
**Date:** 2026-08-24
**Decision owners:** Chief Architect / ML Engineer / Interop Engineer

## Context

MAPLE can call providers but cannot select a fallback by declared capability,
and it has no native golden-case or trajectory evaluation contract. Without
those surfaces, structured output and tool-use regressions are difficult to
detect before release.

## Decision

Add:

- `ProviderCapabilities`, `ProviderRequirements`, and `ProviderRouter` for
  explicit capability matching and deterministic fallback initialization;
- `EvalCase`, `EvalObservation`, `EvalResult`, `EvalReport`, and
  `EvaluationHarness` for local deterministic output-schema and tool-trajectory
  checks;
- bounded/redacted evaluation report values and structured per-case failures.

The router does not infer capabilities from provider names or silently retry
arbitrary providers. Providers must declare capabilities and callers must supply
configurations. The harness does not call a model itself; callers provide a
runner, keeping evaluation fixtures deterministic and credential-free.

## Consequences

Provider integrations gain a stable compatibility/fallback seam, while model
quality remains an application or hosted-eval concern. Evaluation results are
useful release evidence but are not a statistical quality claim without a
representative fixture set.
