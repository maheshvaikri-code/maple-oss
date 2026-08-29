# Slice 184 plan — bounded deterministic trace scoring

**Status:** in progress  
**Date:** 2026-08-28

## Design

- [x] Define a local-only, identifier-free trace projection.
- [x] Define deterministic name/status/parent component scoring.
- [x] Define bounds, error taxonomy, and compatibility surface in ADR-129.

## Implementation

- [ ] Add `TraceEvalSpan` and `TraceEvalCase` validation.
- [ ] Add native `TraceSpan` projection and `EvaluationHarness.run_trace(...)`.
- [ ] Export the new public types.
- [ ] Add focused regression tests.

## Verification and release evidence

- [ ] Run focused trace/evaluation regressions.
- [ ] Run Black, isort, Ruff, mypy, compileall, and diff/security checks.
- [ ] Run the full workspace regression.
- [ ] Update API/README/parity/changelog and review/QA evidence.
- [ ] Rebuild a clean source archive and package smoke-test it.
- [ ] Keep publication, cloud, and website actions out of scope.
