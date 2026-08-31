# Slice 190 plan - authenticated remote task queue statistics

**Status:** complete
**Date:** 2026-08-29

## Design

- [x] Define the fixed `QueueStats` response and `task:read` contract.
- [x] Reserve `/v1/tasks/stats` before task-ID inspection.
- [x] Keep aggregation, dashboards, alerts, scheduling, and queue lifecycle
  outside the boundary.

## Implementation

- [x] Add bounded queue-statistics serialization and validation.
- [x] Add the authenticated server route and client method.
- [x] Add scope, response, malformed-value, and compatibility regressions.

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
