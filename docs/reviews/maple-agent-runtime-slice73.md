# Slice 73 Review - Bounded Per-Goal Token Accounting

**Role:** Code Reviewer / Backend / Security
**Commit:** `2328b92`
**Date:** 2026-08-25

## Findings

- `Goal.token_usage` provides an inspectable aggregate without changing the
  existing `Goal` constructor contract.
- `AutonomousConfig.max_total_tokens` is opt-in, validates positive integer
  input, and does not add a dependency or provider-specific coupling.
- Provider usage is validated before mutation and before tool execution when a
  budget is configured; missing and malformed usage fail closed.
- The same accounting helper covers synchronous, asynchronous, and reflection
  responses, with explicit structured error types.
- Regression tests prove budget overflow prevents both sync and async tool
  handlers from running and that reflection tokens are included.

## Verification

The focused agent/session regression reports `30 passed in 0.31s`. Changed-file
Ruff, Black, isort, and mypy checks pass. Public docs and ADR-025 are filed;
no external or publication action was taken.

## Decision

PASS for the changed boundary. The budget is deliberately provider-backed and
per ReAct goal; cost conversion, team-wide budgets, and standalone decomposition
accounting remain explicit follow-on capabilities. Fresh-context verification
and exact full-suite completion remain release gates.
