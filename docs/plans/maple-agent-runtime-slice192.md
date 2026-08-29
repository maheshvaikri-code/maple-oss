# Slice 192 plan - whole-package type-boundary closure

**Status:** proposed
**Date:** 2026-08-29

## Design

- [x] Preserve runtime behavior and public compatibility.
- [x] Narrow optional bounded copies before constructing successful results.
- [x] Use an explicit result annotation at the dynamic handoff boundary.

## Implementation

- [x] Close the two invocation-store response-narrowing diagnostics.
- [x] Close the remote handoff result-variable diagnostic.
- [x] Add no new dependencies or suppressions.

## Verification and release evidence

- [ ] Run focused invocation and server regressions.
- [ ] Run whole-package mypy and changed-boundary formatting, lint, and compile
  checks.
- [ ] Run the full workspace regression.
- [ ] Update release/parity review and QA evidence.
- [ ] Build and package-smoke-test the current source tree.
- [ ] Rebuild a clean source archive and package-smoke-test it at the
  implementation commit.
- [x] Keep publication, cloud, and website actions out of scope.
