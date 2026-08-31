# Slice 76 QA - Async Orchestration Deadlines and Cancellation

**Role:** Backend / QA / Security / Release  
**Commit:** `7630839`  
**Date:** 2026-08-25

## Scope

Add a request-wide timeout and cooperative cancellation contract to async
supervised and consensus orchestration without changing default behavior.

## Evidence

- Orchestrator regression: `24 passed in 0.43s`.
- Core/autonomy regression: `257 passed in 3.60s`.
- `ruff check maple`: all checks passed.
- Black reports both changed files unchanged after formatting.
- Mypy reports `Success: no issues found in 93 source files`.
- `python -m compileall -q maple` passed.

## Boundary review

- `timeout_seconds` is validated at the public async boundary and applies to
  decomposition, fan-out, result collection, and consensus synthesis.
- `CancellationToken` cancellation returns `ORCHESTRATION_CANCELLED`; expiry
  returns `ORCHESTRATION_TIMEOUT`; invalid values return
  `ORCHESTRATION_CONFIG_INVALID`.
- Native async children are canceled and drained before the orchestration call
  returns. Sync-only executor fallbacks are explicitly not hard-killed because
  Python cannot safely terminate a running thread.
- Existing calls without new keyword arguments retain bounded concurrency,
  stable ordering, and per-member exception isolation.
- No dependency, provider, cloud, publication, or website change was made.

## Decision

PASS for the slice. ADR-028 records the lifecycle and cooperative-cancellation
tradeoff. Exact full-suite completion and fresh independent verification remain
open release gates.
