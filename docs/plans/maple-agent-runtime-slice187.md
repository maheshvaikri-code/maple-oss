# Slice 187 plan — non-blocking remote claim-next

**Status:** in progress
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

- [ ] Run focused autonomy/server and task-management regressions.
- [ ] Run changed-boundary formatting, lint, type, compile, and security checks.
- [ ] Run the full workspace regression.
- [ ] Update API/README/parity/changelog and fresh review/QA evidence.
- [ ] Build and package-smoke-test the current source tree.
- [ ] Rebuild a clean source archive and package-smoke-test it after the implementation/evidence commit.
- [x] Keep publication, cloud, and website actions out of scope.
