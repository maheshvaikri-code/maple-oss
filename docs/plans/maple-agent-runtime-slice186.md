# Slice 186 plan — authenticated remote task-queue control plane

**Status:** complete
**Date:** 2026-08-28

## Design

- [x] Define additive task routes and `task:*` scope mapping.
- [x] Define bounded request/result envelopes and principal policy checks.
- [x] Keep scheduling, execution, retry, and exactly-once effects outside scope.

## Implementation

- [x] Add optional authenticated `TaskQueue` wiring to `RunServer`.
- [x] Add submit/list/inspect/claim/complete/fail server routes.
- [x] Add matching `RunClient` methods and stable task envelopes.
- [x] Add focused authorization, ownership, malformed-input, and compatibility regressions.

## Verification and release evidence

- [x] Run focused autonomy/server and task-management regressions.
- [x] Run changed-boundary formatting, lint, type, compile, and security checks.
- [x] Run the full workspace regression.
- [x] Update API/README/parity/changelog and fresh review/QA evidence.
- [x] Build and package-smoke-test the current source tree.
- [x] Rebuild a clean source archive and package-smoke-test it after the implementation/evidence commit.
- [x] Keep publication, cloud, and website actions out of scope.
