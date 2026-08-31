# Slice 184 plan — bounded deterministic trace scoring

**Status:** complete
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
- [x] Rebuild a clean source archive and package smoke-test it.
- [x] Keep publication, cloud, and website actions out of scope.

## Closure evidence

Implementation commit: `a85ca55`
Public/docs commit: `e3dc496`

```text
focused evaluation/observability: 50 passed in 0.51s
full workspace: 1732 passed, 1 skipped in 292.49s
clean archive: source_archive_entries=859
clean archive suite: 1615 passed, 1 skipped in 262.25s
build_exit=0
wheel_entries=107
sdist_entries=773
twine_exit=0
install_exit=0
version=1.1.3
trace_eval=TraceEvalCase
import_exit=0
doctor_exit=0
```

The clean archive doctor returned all checks true, `network=false`,
`ready=true`, and `status=SUCCESS`. No publication, cloud, or website action
was performed.
