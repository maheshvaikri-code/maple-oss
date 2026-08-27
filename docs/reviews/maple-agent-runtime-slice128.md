# Code Review — Slice 128 @ `3409f39`

**Reviewer role:** Code Reviewer · **Date:** 2026-08-27
**Reviewed against:** [ADR-074](../adr/074-bounded-durable-event-journal.md),
[release plan](../plans/maple-agent-runtime-release.md)
**Diff reviewed:** `e92237d..3409f39`, read from disk after the author pass

## Executed

```text
20 passed in 0.78s
1329 passed, 1 skipped in 270.82s (0:04:30)
All checks passed!                         # Ruff
Success: no issues found in 1 source file # mypy events.py --follow-imports=skip
1 file would be left unchanged.            # Black --check test/source boundary
clean archive no-dependency event journal export smoke passed
```

## Findings

| # | Sev | Location | Finding | Suggested fix | Resolution |
|---|---|---|---|---|---|
| — | — | — | No BLOCKER, MAJOR, MINOR, or NIT findings remain. | — | Clean after timestamp validation fix `032429f`; focused and exact tracked suites re-run. |

## Scope check

The diff matches Slice 128: `EventJournal`/`FileEventJournal`, optional
`EventStream(journal=...)`, startup hydration, publish serialization, bounded
atomic persistence, fencing lease use, public exports, regression tests, ADR,
API/README/parity/changelog updates, and release evidence. It does not add a
remote dependency, cloud service, hosted aggregation, unbounded log, or
exactly-once effect claim.

Correctness passes checked sequence continuity, retention and cursor expiry,
redaction before persistence and on hydration, malformed JSON/state, byte and
shape bounds, callback ordering, journal failure isolation, and lease-backed
atomic replacement. Design remains explicit that multiple writers do not share
a sequence allocator and that remote replay is deferred.

## Verdict

- [x] Pass (0 BLOCKER, MAJORs resolved/waived)

The implementation is genuinely clean against the slice because every new
public path has bounded validation and typed failure handling, durable append
precedes observable side effects, the restart behavior is regression-tested,
the public contract is documented, and the exact tracked test/static/package
gates executed successfully.
