# Slice 191 plan - owner-safe authenticated remote task start

**Status:** complete
**Date:** 2026-08-29

## Design

- [x] Define an owner-checked `ASSIGNED` -> `RUNNING` transition.
- [x] Reuse queue-owned timestamps and statistics accounting.
- [x] Keep heartbeats, leases, scheduling, and distributed coordination out of
  the contract.

## Implementation

- [x] Add the queue and durable-queue lifecycle method.
- [x] Add the authenticated server route and client method.
- [x] Add owner, state, scope, timestamp, statistics, and durable regressions.

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
