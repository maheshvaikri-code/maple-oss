# ADR-081: Bounded Async Evaluation Judges

Status: Accepted for preview

Date: 2026-08-27

## Context

MAPLE's evaluation harness supports deterministic synchronous runners and an
optional host-supplied judge. Agent frameworks commonly need to evaluate an
already asynchronous agent or call an asynchronous provider-owned judge, but
forcing those callbacks through a synchronous adapter makes event-loop use
awkward and can encourage unsafe re-execution.

## Decision

Add `EvaluationHarness.run_async(...)` and the `AsyncEvalJudge` type. The
runner and judge may each be synchronous or awaitable. Cases execute
sequentially in fixture order, and each runner result is immediately passed
through the existing deterministic validation, redaction, and size limits
before the next case is started. A judge receives only the bounded redacted
`EvalObservation` retained by the corresponding `EvalResult`.

The async path preserves the synchronous error taxonomy for runner failures,
judge failures, malformed results, and invalid observations. Async judge
success contributes one additional pass/fail check and its bounded score and
rationale are reported exactly like the synchronous judge. Actual tool names
are retained in `EvalResult` so name-only observations remain available to an
async judge without exposing raw runner values.

The callback is host-owned. MAPLE does not select a provider, retry or fan out
callbacks, persist raw observations, calibrate scores, infer semantic
faithfulness, execute generated code, or provide hosted trace evaluation.

## Alternatives considered

| Alternative | Decision |
| --- | --- |
| Require hosts to wrap async callbacks in sync adapters | Rejected: it creates event-loop hazards and obscures callback failure boundaries. |
| Run the existing sync harness in a worker thread | Rejected: it hides cancellation and adds an unnecessary scheduling boundary. |
| Add provider-specific judge clients | Rejected: provider choice and credentials remain host-owned. |
| Parallelize all cases by default | Deferred: deterministic order and bounded callback ownership are safer defaults. |

## Security and failure boundaries

- Each case is processed through the existing JSON, trajectory, redaction, and
  `max_value_bytes` limits before judge exposure.
- Runner and judge exceptions become typed per-case failures; cancellation is
  not swallowed by the `Exception` boundary.
- No retry, persistence, hosted service, provider selection, or exactly-once
  evaluation claim is introduced.
