# MAPLE Agent Runtime Slice 175 Plan

**Objective:** Add authenticated remote durable checkpoint export and restore.
**Class:** L
**Status:** In progress
**Owner:** Chief Architect

## Gates

- [x] Architecture and threat boundary recorded in ADR-120.
- [x] Public API and wire shape bounded in the slice brief.
- [ ] Implement server routes and client methods.
- [ ] Add authorization, identity, malformed-input, CAS, and round-trip tests.
- [ ] Update API reference, parity ledger, README, changelog, and release plan.
- [ ] Run review/security/QA evidence and package gates.
- [ ] Keep publication, cloud, and website actions out of scope.

## Implementation notes

Use the existing `AgentRunCheckpoint` serializer/parser and built-in store
version fencing. Keep `inspect_agent_run()` metadata-only. The export response
is the only route that returns messages and reasoning trace, and it is gated
by `agent:restore`; the restore response contains only operational metadata.
Reject every invalid condition before calling `save()`. The route must remain
compatible with legacy stores that implement only `load()` for inspection by
returning an explicit restore-unavailable error.

## Validation evidence to collect

- Focused remote checkpoint tests.
- YAML/format/lint/type/compile checks for changed surfaces.
- Full repository test manifest and targeted secret/dangerous-construct scans.
- Clean git-archive build, Twine checks, isolated install/import, and doctor.
- Known environment governance limits remain reported honestly.
