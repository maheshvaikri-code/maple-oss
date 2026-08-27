# Slice 129 QA — Bounded authenticated event batch transport @ `c542828`

**QA Engineer** · **Security Reviewer** · **Date:** 2026-08-27  
**Build under test:** `c542828` (`feat(events): add authenticated batch transport`)

## Acceptance criteria verification

| # | Criterion | How executed | Evidence (real output) | Pass |
|---|---|---|---|---|
| 1 | Authenticated batch transport accepts 1–100 existing event envelopes, preserves request order, and retains stream-owned redaction/sequence behavior | Focused HTTP server/event suite and exact 100-item boundary test | `50 passed in 21.58s`; batch published indexes `[0, 1]`, sequences `[1, 2]`, secret payload `[REDACTED]`; exactly 100 published successfully | PASS |
| 2 | Malformed batch structure fails before any attempt; malformed items are indexed failures; partial success is explicit | Structural empty/101-item tests, low-level malformed-item request, and client validation tests | `50 passed in 21.58s`; 101-item request returned `400 EVENT_BATCH_INVALID` with stream length unchanged at `100`; malformed item returned `200` with failed index `[1]` and published indexes `[0, 2]` | PASS |
| 3 | Authentication, request/response bounds, typed errors, and no implicit retry remain enforced | Authenticated/unauthorized route tests, existing bounded server/client request paths, static checks | Unauthorized batch returned `UNAUTHORIZED`; Black/isort/Ruff/mypy/compile gates passed; no retry path exists in the client | PASS |
| 4 | Scope remains transport batching only: no remote queue, deduplication, transaction, or exactly-once claim | ADR, API reference, README, parity ledger, and changelog review | `git diff --check HEAD^ HEAD` clean; ADR-075 explicitly defers queue, deduplication, transactions, retries, and exactly-once effects | PASS |
| 5 | Release boundary remains dependency-free and tracked-source-only | Clean `git archive HEAD` build, Twine check, isolated smoke | `wheel_entries=104`, `sdist_entries=571`, both Twine checks `PASSED`, no-dependency event-journal smoke passed, `build_exit=0` | PASS |

## Adversarial & edge matrix

| Input/scenario | Expected | Observed | Pass |
|---|---|---|---|
| Empty batch | Typed structural error; no event attempt | `EVENT_BATCH_INVALID`; stream remained unchanged | PASS |
| Exactly 100 items | Accepted at documented limit | 100 published with final sequence `100` | PASS |
| 101 items | Typed structural error before attempts | `400 EVENT_BATCH_INVALID`; no 101st write | PASS |
| Missing event field | Indexed per-item failure for a structurally valid batch | Failed index `1`, `EVENT_INPUT_INVALID`; neighboring items published | PASS |
| Invalid client item/run ID | Local typed validation; no network call | `EVENT_BATCH_INVALID` / `EVENT_INPUT_INVALID` | PASS |
| Secret-bearing payload | Redaction before retention and response | Response and retained stream contained `[REDACTED]` | PASS |
| Unauthorized caller | No event ingestion | `UNAUTHORIZED`; stream sequence remained unchanged | PASS |
| Duplicate/out-of-order results | Preserve request order and host-owned sequence allocation | Published response indexes and stream sequences were ordered; no client-side retry/reordering | PASS |
| Concurrent/failed downstream behavior | Existing `EventStream` locking/failure semantics remain authoritative | Full tracked manifest passed; no new bypass around `stream.publish` | PASS |

## Regression

Focused server/event suite:

```text
50 passed in 21.58s
```

Exact tracked manifest:

```text
1333 passed, 1 skipped in 284.61s (0:04:44)
```

Static and security gates:

```text
2 files would be left unchanged.                 # Black --check
All checks passed!                                # isort
All checks passed!                                # Ruff
Success: no issues found in 1 source file         # mypy server.py --follow-imports=skip
secret_scan: no high-confidence credential patterns in slice diff
dangerous_construct_scan: no new eval/exec/pickle/unsafe-yaml/shell/disabled-TLS patterns in slice diff
No known vulnerabilities found                    # pip_audit . --skip-editable
```

Flakes: none observed in the tracked manifest. The untracked user-owned
Doctrine harness was not included in the release manifest; an aggregate run
including it stalled at that harness and was stopped without altering it.

## Bugs found

| # | Repro steps (minimal) | Severity | Fixed @ | Re-verified | Regression test |
|---|---|---|---|---|---|
| — | — | — | — | No Slice 129 defects found | Boundary, auth, order, redaction, partial-failure, and client-validation tests above |

## Security sweep

The batch route is behind the existing constant-time bearer authorization gate.
It consumes the existing bounded JSON body and response paths, caps the batch
at 100 items, does not echo raw failed input, and delegates every accepted item
to the host-owned `EventStream` for redaction, payload bounds, sequence
allocation, callbacks, exporter delivery, and journal failure semantics.
The client emits only the known event envelope fields and performs no retry.

The slice diff had no high-confidence credential patterns and no new dangerous
construct patterns. `python -m pip_audit . --skip-editable` reported `No known
vulnerabilities found`; no runtime dependency was added. The prior
environment-wide audit finding of `384` known vulnerabilities across `77`
installed packages remains a release-governance veto and is not caused by this
slice.

**Security verdict:** SIGN-OFF · human override: n/a  
**QA verdict:** pass
