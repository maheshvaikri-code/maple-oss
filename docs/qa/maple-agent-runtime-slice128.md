# Slice 128 QA — Bounded durable event journal @ `3409f39`

**QA Engineer** · **Security Reviewer** · **Date:** 2026-08-27
**Build under test:** `3409f39` (`docs(qa): normalize slice128 reports`)

## Acceptance criteria verification

| # | Criterion | How executed | Evidence (real output) | Pass |
|---|---|---|---|---|
| 1 | Optional host-owned journal persists a bounded redacted event window with atomic replacement and fencing | Focused event tests; clean archive build; source review of `FileEventJournal` | `20 passed in 0.78s`; clean archive `build_exit=0`, wheel `104` entries, sdist `570` entries | PASS |
| 2 | Restart rehydrates retained events, reapplies redaction, preserves cursor semantics, and continues sequence numbers | `test_file_event_journal_rehydrates_redacted_events_and_sequence`; cursor-expiry regression | `20 passed in 0.78s`; exact manifest also passed | PASS |
| 3 | Malformed, oversized, non-finite, and non-monotonic records fail closed | Focused malformed-state, journal-size, and invalid-timestamp tests | `20 passed in 0.78s` | PASS |
| 4 | Durable append precedes callbacks/exporters and append failure does not publish in memory | `test_journal_failure_prevents_callbacks_and_memory_publication` | `20 passed in 0.78s` | PASS |
| 5 | Scope remains local bounded replay; no remote aggregation or exactly-once claim | ADR, API reference, README, parity ledger, and changelog review | `git diff --check e92237d..HEAD` clean; no runtime dependency added | PASS |

## Adversarial & edge matrix

| Input/scenario | Expected | Observed | Pass |
|---|---|---|---|
| Empty journal | Construct and publish normally | Covered by restart and failure-path tests; focused suite passed | PASS |
| Huge payload / journal over byte bound | Typed size error; no callback or memory publication | `EVENT_JOURNAL_SIZE`; callback list and snapshot remained empty | PASS |
| Unicode payload | JSON-safe persistence and restart replay | Existing redaction/JSON path plus clean archive smoke exercised import boundary; no encoding failure | PASS |
| Retention at `max_events` and `max_events+1` | Keep bounded tail and expose cursor expiry | Restart restored sequences `[2, 3]`; cursor 0 returned `EVENT_CURSOR_EXPIRED` | PASS |
| Duplicate/out-of-order sequence | Reject without replacing state | Non-monotonic persisted state raised `ValueError`; direct invalid-record tests passed | PASS |
| Non-finite / oversized timestamp | Typed invalid-record error; no file created | Both returned `EVENT_JOURNAL_RECORD_INVALID`; journal path remained absent | PASS |
| Concurrent publication | Serialize sequence allocation and journal writes | Existing event concurrency coverage plus publish lock/lease implementation review; full manifest passed | PASS |
| Interrupted/failed append | No callback/exporter delivery before durable success | Broken journal test observed no callback and empty snapshot | PASS |

## Regression

Focused suite:

```text
20 passed in 0.78s
```

Exact tracked manifest:

```text
1329 passed, 1 skipped in 270.82s (0:04:30)
```

Clean archive package boundary:

```text
wheel entries: 104
sdist entries: 570
clean archive no-dependency event journal export smoke passed
build_exit=0
twine_exit=0
smoke_exit=0
```

Flakes: none observed.

## Bugs found

| # | Repro steps (minimal) | Severity | Fixed @ | Re-verified | Regression test |
|---|---|---|---|---|---|
| 1 | Submit an `AgentEvent` with an integer timestamp too large for `float()` conversion | [MINOR] | `032429f` | Focused suite passed `20` tests | `test_file_event_journal_rejects_nonfinite_and_unrepresentable_records` |

## Security sweep (per `.Doctrine/skills/security.md`)

Secrets scan: no secret-pattern matches in the Slice 128 diff. Injection/path
review: journal path is host-owned, event records are structurally validated,
and writes use `NamedTemporaryFile` plus `os.replace`; no shell/SQL/template
boundary was introduced. Dependency audit: `python -m pip_audit . --skip-editable`
reported `No known vulnerabilities found`; no runtime dependency was added.
Dangerous constructs: no `eval`, `exec`, `pickle`, unsafe YAML, disabled TLS,
or `shell=True` matches in the journal implementation. Bounds/fail-closed:
event count, journal bytes, payload shape/depth, identifiers, timestamps, JSON
serialization, monotonic sequences, atomic writes, fencing leases, and callback
ordering are covered.

**Security verdict:** SIGN-OFF · human override: n/a
**QA verdict:** pass
