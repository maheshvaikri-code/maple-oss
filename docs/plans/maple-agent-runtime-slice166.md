# Implementation Plan - durable receiver-side event deduplication

**Brief:** [maple-agent-runtime-slice166.md](../briefs/maple-agent-runtime-slice166.md)
**Design/ADR:** [ADR-111](../adr/111-durable-event-deduplication.md)
**Class:** L

## Slices

| # | Slice | Role | Files touched | Proven by (tests) | Status |
|---|---|---|---|---|---|
| 1 | File-backed store and protocol-compatible state machine | Backend / Security | `maple/autonomy/events.py`, `tests/autonomy/test_events.py` | Restart replay, pending/abort, conflict, expiry, capacity, malformed state, atomic write failure, and cross-process lease boundary | todo |
| 2 | Public surface and release documentation | Interop / Tech Writer | package exports, README, API reference, parity ledger, changelog, release plan | Import/export smoke, runnable API example, docs consistency, targeted lint | todo |
| 3 | Independent review, QA, security, and package gates | Code Reviewer / Security / QA / Release | `docs/reviews/`, `docs/qa/`, release evidence | Focused + tracked tests, static gates, secret/danger scans, clean archive build, Twine, isolated import | todo |

## Threat sketch

Assets touched: replay claims, source identity, fingerprints, and redacted
destination events. Entry points / untrusted inputs: source IDs and sequences,
source/destination event JSON, store directory contents, wall-clock values,
and concurrent local processes. Worst plausible abuse: an attacker or fault
replaces the state file, submits conflicting content, exhausts bounded
capacity, or races a completion to cause duplicate publication; strict parse,
atomic replacement, bounded state, and the durable lease fail closed.

## Risks & rollback points

- Risk: persisted schema rejects a preexisting file or writes a partial record
  -> mitigation: versioned full-state validation, temp-file fsync, atomic replace
  -> rollback: remove only the new public export/implementation commit; the
  existing in-memory store remains unchanged.
- Risk: the store is mistaken for exactly-once infrastructure
  -> mitigation: API docs, parity ledger, and ADR explicitly limit claims
  -> rollback: none needed; correct the documentation before release.
- Risk: a local lease outage blocks event receiver progress
  -> mitigation: typed fail-closed lease errors and existing caller retry
  -> rollback: configure the prior in-memory store for single-process hosts.

## Deviation log (append-only, as they happen)

- None.

## Status snapshot

Done (with evidence): brief and ADR accepted; next: implement the durable
store and regressions; blocked on: none.
