# Implementation Plan - Typed Remote Agent-Run Lifecycle

**Brief:** [Slice168 brief](../briefs/maple-agent-runtime-slice168.md)
**Design/ADR:** [ADR-113](../adr/113-typed-remote-agent-lifecycle.md)
**Class:** M

## Slices

| # | Slice | Role | Files touched | Proven by (tests) | Status |
|---|---|---|---|---|---|
| 1 | Shared bounded remote run-envelope normalizer and typed client methods | Backend / Interop / Security | `maple/autonomy/server.py`, exports if needed | Valid completed/paused/failed/cancelled envelopes, identity mismatch, malformed and invalid cancel responses | done: `2726fab` |
| 2 | Regression coverage and public contract documentation | QA / Tech Writer | `tests/autonomy/test_server.py`, API docs, README, changelog, parity ledger | Focused lifecycle tests, tracked regression, docs/export smoke | done: focused `85 passed in 19.78s`; tracked `1523 passed, 1 skipped`; docs `77b2d2b` |
| 3 | Review, QA, security, package, and release evidence | Code Reviewer / Security / QA / Release | `docs/reviews/`, `docs/qa/`, release plan | Static, secret/danger, archive, Twine, isolated install/import, and release checks | done: review/QA filed; clean archive at `77b2d2b` passed |

## Risks and rollback points

- Risk: a malformed remote envelope is accidentally exposed as a typed run ->
  mitigation: shared identity and bounded normalization before construction ->
  rollback: remove only the additive methods and helper.
- Risk: callers confuse typed error state with a successful run -> mitigation:
  preserve `AgentRun.error`, document status semantics, and require `cancelled`
  for typed cancellation -> rollback: retain the raw methods as the stable
  compatibility path.
- Risk: the new API is mistaken for remote persistence or exactly-once effects
  -> mitigation: explicit non-goals in the brief, ADR, API docs, parity ledger,
  README, and changelog.

## Deviation log (append-only, as they happen)

- None.

## Status snapshot

Done (with evidence): design, implementation, regressions, public
documentation, review, QA/security, and clean-archive package gate. Next:
select the next highest-value parity/release-readiness slice. Blocked on:
publication authorization remains closed by repository governance.
