# Code Review — Slice 129 @ `c542828`

**Reviewer role:** Code Reviewer · **Date:** 2026-08-27  
**Reviewed against:** [ADR-075](../adr/075-bounded-authenticated-event-batching.md),
[release plan](../plans/maple-agent-runtime-release.md)  
**Diff reviewed:** `70b5e37..c542828`, read from disk after the author pass

## Executed

```text
50 passed in 21.58s
1333 passed, 1 skipped in 284.61s (0:04:44)
All checks passed!                         # isort/Ruff
Success: no issues found in 1 source file # mypy server.py --follow-imports=skip
2 files would be left unchanged.         # Black --check
build_exit=0
twine_exit=0
```

## Findings

| # | Sev | Location | Finding | Suggested fix | Resolution |
|---|---|---|---|---|---|
| — | — | — | No BLOCKER, MAJOR, MINOR, or NIT findings remain. | — | Clean after focused and exact tracked suites plus static/package gates. |

## Scope check

The diff matches Slice 129: ADR-075, the bounded authenticated
`POST /v1/events/batch` route, `RunClient.publish_events(...)`, indexed
partial-success results, shared event input validation, regression tests, and
API/README/parity/changelog/release evidence. It does not add a broker, retry
loop, deduplication key, remote durable queue, cloud service, or exactly-once
effect claim.

Correctness passes checked authentication before dispatch, whole-batch shape
validation before attempts, per-item validation without raw-input echo,
request-order submission through the existing stream boundary, redaction and
sequence preservation, partial success, 100/101 boundaries, client-side
normalization, and the existing body/response caps. The public contract is
documented and no dependency or unrelated API surface was changed.

## Verdict

- [x] Pass (0 BLOCKER, MAJORs resolved/waived)

The implementation is clean against the slice because it adds only bounded
transport overhead reduction, preserves the host-owned event semantics, makes
partial delivery explicit, and has executed regression, security, static, and
package-boundary evidence.
