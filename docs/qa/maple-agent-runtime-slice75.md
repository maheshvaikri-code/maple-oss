# Slice 75 QA - Bounded Structured-Output Repair

**Role:** ML Engineer / Backend / QA / Security / Release
**Commit:** `e3becdf`
**Date:** 2026-08-25

## Scope

Add opt-in correction attempts for invalid structured/typed model output and
output-guardrail rejection while preserving fail-fast defaults and existing
token/step budgets.

## Evidence

- Agent regression: `28 passed in 0.33s`.
- `ruff check maple/autonomy/agent.py tests/autonomy/test_agent.py`: all checks
  passed.
- Black, isort, and `python -m mypy maple/autonomy/agent.py
  --ignore-missing-imports`: passed.

## Boundary review

- `max_output_retries` is additive, validated from 0 through 3, and defaults to
  0 so existing invalid-output behavior remains fail-fast.
- Sync and async ReAct loops use the same bounded correction behavior.
- Each correction is a normal model response, appears in the reasoning trace,
  consumes a reasoning step and provider usage, and can exceed the goal token
  budget before any later tool execution.
- Exhausted retries return the original structured error; retry prompts expose
  only a controlled error type and not validation payloads.
- No model/provider/dependency change or external service action was made.

## Decision

PASS for the slice. ADR-027 records the bounded repair tradeoff. This is a
deterministic contract test, not a claim of semantic model-quality improvement;
the exact full-suite and fresh verifier gates remain open.
