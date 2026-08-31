# Code Review — Slice 130 @ `9e74115`

**Reviewer role:** Code Reviewer · **Date:** 2026-08-27
**Reviewed against:** [ADR-076](../adr/076-bounded-durable-event-forwarding.md),
[release plan](../plans/maple-agent-runtime-release.md)
**Diff reviewed:** `3b1c1f2..9e74115`, read from disk after the author pass

## Executed

```text
31 passed in 2.70s                         # focused event suite
61 passed in 15.24s                        # event + server suites
1344 passed, 1 skipped in 245.95s          # exact tracked manifest
4 files would be left unchanged.           # Black --check
All checks passed!                          # Ruff
Success: no issues found in 1 source file  # mypy events.py --follow-imports=skip
build_exit=0
twine_exit=0
```

## Findings

| # | Sev | Location | Finding | Suggested fix | Resolution |
|---|---|---|---|---|---|
| — | — | — | No BLOCKER, MAJOR, MINOR, or NIT findings remain. | — | Clean after focused, exact tracked, static, security, and package-boundary gates. |

## Scope check

The diff matches Slice 130: bounded `EventForwarder` orchestration,
in-memory and atomic fenced file cursor stores, authenticated
`HttpEventBatchSender`, complete indexed acknowledgement validation,
contiguous-prefix cursor advancement, regression tests, public exports, and
release documentation. It does not add a hosted scheduler, remote queue,
deduplication protocol, cross-forwarder ordering, or exactly-once effect
claim.

Correctness checks covered source retention gaps, cursor expiry and rollback,
cursor-save failures, serialized forwarder calls, partial delivery, malformed
or incomplete acknowledgements, request/response bounds, HTTPS/authentication,
re-redaction, and restart rehydration through an authenticated `RunServer`.
Only the contiguous acknowledged prefix advances the durable cursor, so later
successes cannot silently skip an earlier failure.

## Verdict

- [x] Pass (0 BLOCKER, MAJORs resolved/waived)

The implementation is clean against the slice. Its at-least-once behavior is
explicit, bounded, host-owned, and documented; transport or cursor failures
leave the source cursor unchanged or advanced only through the verified
contiguous prefix.
