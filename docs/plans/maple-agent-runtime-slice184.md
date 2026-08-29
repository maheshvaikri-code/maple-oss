# Slice 184 plan — bounded deterministic trace scoring

**Status:** verification complete; package gate pending
**Date:** 2026-08-28

## Design

- [x] Define a local-only, identifier-free trace projection.
- [x] Define deterministic name/status/parent component scoring.
- [x] Define bounds, error taxonomy, and compatibility surface in ADR-129.

## Implementation

- [x] Add `TraceEvalSpan` and `TraceEvalCase` validation.
- [x] Add native `TraceSpan` projection and `EvaluationHarness.run_trace(...)`.
- [x] Export the new public types.
- [x] Add focused regression tests.

## Verification and release evidence

- [x] Run focused trace/evaluation regressions.
- [x] Run Black, isort, Ruff, mypy, compileall, and diff/security checks.
- [x] Run the full workspace regression.
- [x] Update API/README/parity/changelog and review/QA evidence.
- [ ] Rebuild a clean source archive and package smoke-test it.
- [ ] Keep publication, cloud, and website actions out of scope.
