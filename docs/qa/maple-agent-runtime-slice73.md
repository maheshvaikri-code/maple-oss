# Slice 73 QA - Bounded Per-Goal Token Accounting

**Role:** Backend / QA / Security / Release
**Commit:** `2328b92`
**Date:** 2026-08-25

## Scope

Add opt-in aggregate provider usage and hard token budgets to synchronous and
asynchronous autonomous ReAct goals, including reflection calls.

## Evidence

- Agent/session regression: `30 passed in 0.31s`.
- `ruff check maple/autonomy/agent.py tests/autonomy/test_agent.py`: all checks
  passed.
- Black, isort, and `python -m mypy maple/autonomy/agent.py
  --ignore-missing-imports`: passed.

## Boundary review

- `Goal.token_usage` is additive and defaults to zero, preserving existing
  callers that construct goals positionally.
- `max_total_tokens` is opt-in and validates as a positive integer; the default
  `None` preserves provider compatibility.
- A configured budget requires provider usage and rejects missing, negative,
  boolean, or non-integer usage values with structured errors.
- Reasoning and reflection usage are both counted in sync and async loops.
- A budget overrun returns before the response's tools execute; sync and async
  tests verify the handler side effect does not occur.
- No cost service, new dependency, credential, cloud call, publication, or
  website mutation was introduced.

## Decision

PASS for the slice. ADR-025 records the provider-backed budget tradeoff and
the explicit boundary around standalone goal decomposition. Exact full-suite
and fresh verifier gates remain open.
