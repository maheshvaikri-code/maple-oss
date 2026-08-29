# Slice 185 plan — bounded durable local task queue

**Status:** implementation complete; clean archive gate pending
**Date:** 2026-08-28

## Design

- [x] Define the `FileTaskQueue` compatibility and restart contract.
- [x] Define bounded JSON state, atomic write, path, and local fencing rules.
- [x] Define explicit at-least-once recovery and out-of-scope claims in ADR-130.

## Implementation

- [x] Implement bounded task serialization and strict hydration.
- [x] Implement fenced atomic persistence and restart normalization.
- [x] Preserve `TaskQueue`/`TaskScheduler` method compatibility.
- [x] Add failure-path and restart/concurrency regressions.
- [x] Export the durable queue publicly.

## Verification and release evidence

- [x] Run focused task-management regressions.
- [x] Run Black, isort, Ruff, mypy, compileall, and diff/security checks.
- [x] Run the full workspace regression.
- [x] Update API/README/parity/changelog and review/QA evidence.
- [x] Build and package-smoke-test the current source tree.
- [ ] Rebuild a clean source archive and package smoke-test it after the
  implementation/evidence commit.
- [x] Keep publication, cloud, and website actions out of scope.
