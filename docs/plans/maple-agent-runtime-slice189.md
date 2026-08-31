# Slice 189 plan - owner-safe remote task retry

**Status:** complete
**Date:** 2026-08-29

## Design

- [x] Define the `task:retry` scope and additive route/client contract.
- [x] Restrict owner-aware remote retry to failed tasks.
- [x] Keep automatic retry, scheduling, lease control, and federation
  outside the boundary.

## Implementation

- [x] Add owner-aware requeue for in-memory and durable queues.
- [x] Add the authenticated server route and client method.
- [x] Add authorization, owner/state, bound, malformed-input, and
  compatibility regressions.

## Verification and release evidence

- [x] Run focused server and task-management regressions.
- [x] Run changed-boundary formatting, lint, type, compile, and security
  checks.
- [x] Run the full workspace regression.
- [x] Update API/README/parity/changelog and review/QA evidence.
- [x] Build and package-smoke-test the current source tree.
- [x] Rebuild a clean source archive and package-smoke-test it at the
  implementation commit.
- [x] Keep publication, cloud, and website actions out of scope.
