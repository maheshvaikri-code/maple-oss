# Slice 184 brief — bounded deterministic trace scoring

**Date:** 2026-08-28  
**Class:** L  
**Role:** Chief Architect  
**Status:** proposed

## Objective

Close the local trace-scoring gap in the evaluation surface without selecting a
model provider or creating a trace persistence boundary. Hosts need a stable
way to assert that an agent emitted the expected bounded span structure.

## In scope

- versioned `TraceEvalCase` fixtures with bounded expected spans;
- conversion of native `TraceSpan` values into identifier-free evaluation spans;
- deterministic positional scoring for span name, status, and parent structure;
- fail-closed runner, fixture, sequence, and score-bound validation;
- reuse of the existing bounded `EvalReport`/`EvalResult` shape;
- tests, public exports, API documentation, parity ledger, changelog, and QA
  evidence.

## Out of scope

- semantic faithfulness or causal correctness claims;
- model/provider judges, calibration, threshold tuning, or retries;
- trace payload, prompt, tool argument, or attribute persistence;
- remote or hosted trace search, aggregation, scheduling, or storage;
- generated-code execution, browser/computer use, or website/publication work.

## Acceptance criteria

1. A host can score a bounded sequence of `TraceSpan` values against a
   versioned fixture through `EvaluationHarness.run_trace(...)`.
2. The score is deterministic and decomposes into name, status, and parent
   structure components; missing or extra spans lower the score.
3. Native span IDs and attributes are not exposed in evaluation results.
4. Invalid fixtures, malformed observations, over-limit sequences, exceptions,
   and below-threshold scores become typed bounded failures.
5. Existing output, trajectory, retrieval, groundedness, and judge behavior
   remains compatible.
6. Focused and full regressions, formatting, lint, type, compile, package, and
   local doctor gates are recorded before closure.

## Threat sketch

Assets are evaluation integrity and bounded diagnostic metadata. Entry points
are fixture construction and the host-supplied trace runner. The plausible
abuse is oversized or malformed trace input, or accidental disclosure through
trace IDs/attributes. Fixed span quotas, scalar identifier-free projections,
finite scores, and no remote/payload persistence contain the boundary.

## Evidence plan

- focused `tests/autonomy/test_evaluation.py` trace regressions;
- full workspace `python -m pytest -q --no-cov`;
- Black, isort, Ruff, mypy, compileall, diff checks, and source scans;
- clean committed-HEAD source archive/package install and network-free doctor
  smoke, with no publication or website action.
