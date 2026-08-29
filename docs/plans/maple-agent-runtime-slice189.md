# Slice 189 plan - owner-safe remote task retry

**Status:** proposed
**Date:** 2026-08-29

## Design

- [x] Define the `task:retry` scope and additive route/client contract.
- [x] Restrict owner-aware remote retry to failed tasks.
- [x] Keep automatic retry, scheduling, lease control, and federation
  outside the boundary.

## Implementation

- [ ] Add owner-aware requeue for in-memory and durable queues.
- [ ] Add the authenticated server route and client method.
- [ ] Add authorization, owner/state, bound, malformed-input, and
  compatibility regressions.

## Verification and release evidence

- [ ] Run focused server and task-management regressions.
- [ ] Run changed-boundary formatting, lint, type, compile, and security
  checks.
- [ ] Run the full workspace regression.
- [ ] Update API/README/parity/changelog and review/QA evidence.
- [ ] Build and package-smoke-test the current source tree.
- [ ] Rebuild a clean source archive and package-smoke-test it at the
  implementation commit.
- [x] Keep publication, cloud, and website actions out of scope.
