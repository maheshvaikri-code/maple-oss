# Slice 191 plan - owner-safe authenticated remote task start

**Status:** proposed
**Date:** 2026-08-29

## Design

- [x] Define an owner-checked `ASSIGNED` -> `RUNNING` transition.
- [x] Reuse queue-owned timestamps and statistics accounting.
- [x] Keep heartbeats, leases, scheduling, and distributed coordination out of
  the contract.

## Implementation

- [ ] Add the queue and durable-queue lifecycle method.
- [ ] Add the authenticated server route and client method.
- [ ] Add owner, state, scope, timestamp, statistics, and durable regressions.

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
