# Slice 130 QA — Bounded durable event forwarding @ `9e74115`

**QA Engineer** · **Security Reviewer** · **Date:** 2026-08-27
**Build under test:** `9e74115` (`feat(events): add durable remote forwarding`)

## Acceptance criteria verification

| # | Criterion | How executed | Evidence (real output) | Pass |
|---|---|---|---|---|
| 1 | Forward at most 100 retained events through a host-selected sender and advance only the contiguous acknowledged prefix | Event-forwarder unit tests plus authenticated destination restart test | `31 passed in 2.70s`; batches were capped at `2` in the restart test, the cursor rehydrated, and remote sequences remained ordered | PASS |
| 2 | Durable cursor state is bounded, atomic, fenced, non-regressing, and fail-closed on malformed state or expiry | In-memory/file cursor tests, malformed-state test, cursor-save failure test, and source retention-gap test | `61 passed in 15.24s`; malformed state, expired source cursor, and save failure produced typed errors without sender dispatch or silent advancement | PASS |
| 3 | Remote HTTP delivery is authenticated, bounded, HTTPS-protected, re-redacted, and validates a complete indexed acknowledgement | HTTP sender redaction, bounds, incomplete-ack, and server integration tests | `61 passed in 15.24s`; request/response limits and incomplete acknowledgements failed closed; remote payloads contained `[REDACTED]` | PASS |
| 4 | Failure semantics remain explicit: no implicit retry, remote queue, deduplication, cross-forwarder ordering, or exactly-once effect claim | ADR, API reference, README, parity ledger, changelog, and source review | `git diff --check HEAD^ HEAD` clean; ADR-076 documents at-least-once delivery and the deferred capabilities | PASS |
| 5 | Release boundary remains tracked-source-only and dependency-free | Clean `git archive HEAD` build, Twine check, entry counts, and isolated `python -S` smoke | `build_exit=0`; wheel `104` entries; sdist `574` entries; both Twine checks `PASSED`; no-dependency durable-forwarder smoke passed | PASS |

## Adversarial & edge matrix

| Input/scenario | Expected | Observed | Pass |
|---|---|---|---|
| Empty source window | No sender call and unchanged cursor | Forward report was a no-op | PASS |
| Earlier item fails while later item succeeds | Advance only through the earlier contiguous prefix | Later success was not committed; failed item was retried on the next call | PASS |
| Sender transport failure | Cursor remains unchanged | Sender failure returned a typed error and no cursor write | PASS |
| Cursor persistence failure | Do not claim durable advancement | Save failure returned an error; the source cursor remained unchanged | PASS |
| Expired source cursor | Fail closed before delivery | Sender was not called and `EVENT_CURSOR_EXPIRED` surfaced | PASS |
| Incomplete/duplicate/out-of-range acknowledgement | Reject response without advancement | `EVENT_DELIVERY_INVALID`; no partial acknowledgement was accepted | PASS |
| Secret-bearing event | Redact before local retention and remote submission | Retained and remote payloads contained `[REDACTED]` | PASS |
| Destination restart | Rehydrated cursor resumes without source loss | `FileEventJournal` and `FileEventCursorStore` resumed ordered batches | PASS |

## Regression

Focused event suite:

```text
31 passed in 2.70s
```

Event plus server suite:

```text
61 passed in 15.24s
```

Exact tracked manifest:

```text
tracked_test_files=108
1344 passed, 1 skipped in 245.95s (0:04:05)
```

Static, package, and security gates:

```text
4 files would be left unchanged.                 # Black --check
All checks passed!                                # Ruff
Success: no issues found in 1 source file         # mypy events.py --follow-imports=skip
secret_scan: no high-confidence credential patterns in committed Slice 130 diff
dangerous_construct_scan: no new eval/exec/pickle/unsafe-yaml/shell/disabled-TLS patterns in committed Slice 130 diff
No known vulnerabilities found                    # pip_audit . --skip-editable
wheel_entries=104
sdist_entries=574
twine_exit=0
build_exit=0
```

No runtime dependency was added. The project-scoped audit is clean; the
environment-wide audit still reports `384` known vulnerabilities across `77`
installed packages and remains a release-governance veto outside this slice.

## Bugs found

| # | Repro steps (minimal) | Severity | Fixed @ | Re-verified | Regression test |
|---|---|---|---|---|---|
| — | — | — | — | No Slice 130 defects found | Cursor monotonicity, retention expiry, partial delivery, malformed acknowledgement, bounds, redaction, restart, and save-failure tests above |

## Security sweep

The forwarder is opt-in and synchronous. It reads one bounded source window,
re-redacts events before remote submission, uses the existing authenticated
HTTPS transport, and rejects malformed or incomplete indexed acknowledgements.
File cursors use bounded JSON, atomic replacement, non-regressing saves, and
fencing leases. The design intentionally permits duplicate sends after a lost
response or cursor write; it does not pretend to provide exactly-once effects.

The committed slice diff had no high-confidence credential patterns and no new
dangerous construct patterns. `python -m pip_audit . --skip-editable` reported
`No known vulnerabilities found`; no runtime dependency was added. The
environment-wide dependency finding above is a governance veto, not a defect
introduced by Slice 130.

**Security verdict:** SIGN-OFF · human override: n/a
**QA verdict:** pass
