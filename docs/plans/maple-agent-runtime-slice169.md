# Implementation Plan - Native Autonomous-Agent Remote Transport Adapter

**Brief:** [Slice169 brief](../briefs/maple-agent-runtime-slice169.md)
**Design/ADR:** [ADR-114](../adr/114-native-agent-remote-transport-adapter.md)
**Class:** L

## Slices

| # | Slice | Role | Files touched | Proven by (tests) | Status |
|---|---|---|---|---|---|
| 1 | Implement adapter, store binding, Goal-to-AgentRun mapping, and registration | Backend / Interop / Security | `maple/autonomy/agent_transport.py`, autonomy/package exports | Native start/resume binding, invalid identity/status, callback error sanitization, explicit cancellation registration | done: `e1812f6` |
| 2 | Add authenticated integration regressions and public docs | QA / Tech Writer | `tests/autonomy/test_agent_transport.py`, README, API reference, parity ledger, changelog | Remote start/resume through RunServer/RunClient plus raw compatibility and docs/export smoke | done: focused `90 passed in 20.12s`; tracked `1528 passed, 1 skipped`; docs `b3d8f74` |
| 3 | Review, QA, security, package, and release evidence | Code Reviewer / Security / QA / Release | `docs/reviews/`, `docs/qa/`, release plan | Full tracked suite, static/security gates, clean archive, Twine, isolated install/import | done: review/QA filed; clean archive at `b3d8f74` passed |

## Risks and rollback points

- Risk: a native `Goal` is mapped to the wrong remote run -> mitigation:
  require exact agent/run identity and supported terminal/paused status ->
  rollback: remove the adapter module and exports; raw handlers remain.
- Risk: the adapter exposes provider or callback details -> mitigation: map
  callback errors/exceptions to generic typed errors and rely on existing
  bounded `AgentRun` normalization -> rollback: disable native registration.
- Risk: a host assumes adapter registration persists checkpoints -> mitigation:
  bind and document the caller-owned store without synthesizing checkpoints ->
  rollback: require explicit host callback wiring until a separate persistence
  protocol exists.

## Deviation log (append-only, as they happen)

- None.

## Status snapshot

Done (with evidence): design, implementation, integration regressions, public
documentation, review, QA/security, and clean-archive package gate. Next:
select the next highest-value parity/release-readiness slice. Blocked on:
publication authorization remains closed by repository governance.
