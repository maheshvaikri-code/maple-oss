# ADR-077: Bounded structured evaluation trajectories

**Date:** 2026-08-27  
**Status:** accepted  
**Deciders:** Chief Architect, Backend, Security, QA

## Context

MAPLE's evaluation harness can already compare an ordered list of tool names,
but framework evaluation surfaces commonly need to assert more of a run
trajectory: the tool arguments, returned value, terminal status, and bounded
duration. A name-only assertion cannot distinguish a correct tool call from a
call with unsafe or incorrect arguments. Passing raw tool records through a
report or judge would also create an accidental secret and unbounded-data
boundary.

## Decision

Add the additive `EvalTrajectoryStep` value with a bounded tool name, JSON-safe
arguments and result, one of `ok`, `error`, or `cancelled` statuses, and a
finite non-negative duration capped at 24 hours. A step's arguments and result
are capped at 64 KiB, and a trajectory is capped at 256 steps.

`EvalCase.expected_trajectory` accepts a tuple of steps and can be used alone
or alongside the existing `expected_tool_names`; when both are supplied, the
names must match. `EvalObservation.trajectory` accepts the same structured
steps. If `tool_names` is omitted, the harness derives it from the structured
trajectory; if both are present, they must agree. Exact trajectory matching is
performed against the validated host observation before report redaction.

Actual trajectory data is re-redacted and bounded by the harness
`max_value_bytes` limit before it appears in `EvalResult` or reaches an
optional `EvalJudge`. Invalid steps, mismatched name/trajectory pairs, and
oversized redacted reports fail the individual case with typed errors. The
existing two-argument `EvalObservation(output, tool_names)` form remains
valid.

This contract records and evaluates host-supplied data only. MAPLE does not
execute generated code, infer semantic correctness from a trajectory, select
or retry a judge, or claim hosted trace scoring, calibration, or exactly-once
evaluation.

## Alternatives considered

| Option | Pros | Cons | Why not |
|---|---|---|---|
| Add bounded structured steps (chosen) | Exact local checks for arguments/results/status; additive and provider-neutral | Does not provide semantic scoring or hosted trace search | Appropriate dependency-free evaluation boundary |
| Keep tool names only | Smallest API | Cannot assert call data or failure state | Insufficient trajectory coverage for release fixtures |
| Persist/export raw traces | Richer debugging | Creates privacy, retention, and transport obligations | Out of scope for a local evaluation contract |

## Consequences

- Golden fixtures can verify a bounded, meaningful tool trajectory while the
  existing name-only API remains compatible.
- Reports and judges receive redacted structured data, with explicit size and
  step limits.
- Async/provider-owned judges, trace scoring, calibration, hosted evaluation,
  and sandbox execution remain separate reviewed capabilities.
