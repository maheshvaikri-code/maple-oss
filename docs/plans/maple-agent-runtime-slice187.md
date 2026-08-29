# Slice 187 plan — non-blocking remote claim-next

**Status:** complete
**Date:** 2026-08-28

## Design

- [x] Define the bounded claim-next request and `task:claim` scope.
- [x] Define deterministic priority/candidate ordering and race behavior.
- [x] Keep worker lifecycle and scheduling policy host-owned.

## Implementation

- [x] Add the authenticated server route and capability filter.
- [x] Add `RunClient.claim_next_task(...)`.
- [x] Add priority, compatibility, empty-result, and principal-policy regressions.

## Verification and release evidence

- [x] Run focused autonomy/server and task-management regressions.
- [x] Run changed-boundary formatting, lint, type, compile, and security checks.
- [x] Run the full workspace regression.
- [x] Update API/README/parity/changelog and review/QA evidence.
- [x] Build and package-smoke-test the current source tree.
- [x] Rebuild a clean source archive and package-smoke-test it at the implementation commit.
- [x] Keep publication, cloud, and website actions out of scope.
