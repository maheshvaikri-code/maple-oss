# ADR-027: Bounded structured-output repair

**Date:** 2026-08-25
**Status:** accepted
**Deciders:** Chief Architect / ML Engineer

## Context

MAPLE validates structured and typed model output at the agent boundary, but a
validation failure immediately ended the goal. Modern agent runtimes commonly
give the model a bounded opportunity to correct malformed output or a rejected
guardrail result. An unbounded retry would undermine token and step budgets.

## Decision

Add `AutonomousConfig.max_output_retries`, bounded from 0 through 3 and
defaulting to 0. When enabled, a failed structured-output or output-guardrail
validation appends a non-sensitive correction request and continues the ReAct
loop. Every retry is a normal model response: it consumes reasoning steps and
provider token usage, and can therefore hit `max_total_tokens`. Exhausted
retries return the original structured error unchanged.

The correction request includes only the controlled error type, not validation
payloads or model output details. The default remains fail-fast for backward
compatibility and hosts that do not want repair behavior.

## Alternatives considered

| Option | Pros | Cons | Why not |
|---|---|---|---|
| Opt-in bounded correction (chosen) | Useful recovery, explicit cost cap, sync/async parity | Adds another model turn when enabled | Best fit for existing contracts and budgets |
| Always fail fast | Deterministic latency and cost | Poor recovery from common formatting mistakes | Retained as the default, not the only mode |
| Unbounded retry until valid | Highest eventual success probability | Can loop forever and bypass host budgets | Unsafe for a production agent runtime |
| Repair locally without the model | No extra model call | Cannot reliably infer missing semantic fields | Not general enough for typed output |

## Consequences

- Positive: callers can opt into bounded repair for typed models, schemas, and
  output guardrails without changing the existing default.
- Positive: retries are visible in reasoning traces and consume the same token
  and step budgets as all other model responses.
- Negative / debt accepted: repair quality is provider/model-dependent; no
  claim of semantic correctness or automatic prompt optimization is made.
- Invalidation triggers: a need for provider-native structured-output repair,
  richer error localization, or a separately evaluated prompt policy.
