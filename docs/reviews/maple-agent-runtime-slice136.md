# MAPLE Agent Runtime Slice 136 Review Record

Date: 2026-08-27

Scope reviewed: `bfd56b5`, covering `EvaluationHarness.run_async`,
`AsyncEvalJudge`, additive `EvalResult.actual_tool_names`, exports, async
runner/judge regressions, ADR-081, and public docs.

## Findings

- Sync and awaitable runners and judges share one bounded callback contract;
  cases execute sequentially in fixture order.
- Each runner result is processed through the existing deterministic checks and
  redaction path before judge exposure; raw observations are not retained by
  the async orchestration layer across cases.
- Async runner exceptions preserve the existing typed per-case failure and do
  not invoke the judge for that failed case; cancellation is not swallowed by
  the ordinary `Exception` boundary.
- Name-only observations retain bounded tool names in `EvalResult`, so async
  judges receive the same meaningful observation shape as sync judges.
- The slice adds no provider, network, retry, persistence, calibration,
  hosted-trace, generated-code, or exactly-once behavior.
- Focused/full regressions, whole-package typing, changed-surface static and
  security checks, and clean package smoke coverage passed.

## Disposition

Author-side review: no blocking finding for this slice. A fresh independent
review session was not available, so this record is not represented as an
independent verifier approval. Provider-owned judge orchestration, calibration,
trace scoring, semantic faithfulness, and hosted evaluation remain separate
roadmap boundaries.
