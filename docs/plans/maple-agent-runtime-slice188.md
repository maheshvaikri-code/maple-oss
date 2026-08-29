# Slice 188 plan - owner-safe remote task cancellation

**Status:** proposed
**Date:** 2026-08-28

## Design

- [x] Define the `task:cancel` scope and additive route/client contract.
- [x] Define queued, owned, running, and terminal cancellation semantics.
- [x] Keep force termination, lease revocation, retry, and distributed
  coordination outside the boundary.

## Implementation

- [ ] Add owner-aware queue cancellation for in-memory and durable queues.
- [ ] Add the authenticated server route and client method.
- [ ] Add authorization, ownership, terminal-state, malformed-input, and
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
