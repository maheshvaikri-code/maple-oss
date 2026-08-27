# Code Review — MAPLE Agent Runtime Slice 113 @ d26973f

**Reviewer role:** Code Reviewer · **Date:** 2026-08-26
**Reviewed against:** [release brief](../briefs/maple-agent-runtime-release.md),
[release plan](../plans/maple-agent-runtime-release.md), and
[ADR-059](../adr/059-bounded-http-event-exporter.md)
**Review scope:** feature commit `d098e3a` plus the timeout-validation fix
`d26973f`

## Findings

| # | Sev | Location | Finding | Resolution |
|---|-----|----------|---------|------------|
| 1 | [MINOR] | `HttpEventExporter` timeout validation | The first implementation rejected non-positive values but accepted `NaN` and infinite timeout values, which weakened the documented finite-timeout boundary. | Fixed in `d26973f` with finite normalization and regression coverage for `NaN`, positive infinity, and negative infinity. |

No BLOCKER, MAJOR, or unresolved MINOR findings remain.

## Scope check

The final diff adds a dependency-free optional HTTP exporter for already-
redacted `AgentEvent` envelopes. It validates endpoint scheme, host, userinfo,
query/fragment, control characters, bearer-header safety, non-loopback HTTPS,
request/response byte bounds, and finite timeout values. It performs one
synchronous POST, accepts only 2xx responses, performs no retries or
persistence, and remains behind the existing `EventStream` exporter-failure
isolation boundary.

The exporter does not claim hosted trace search, fleet aggregation, durable
replay, batching, exactly-once delivery, certificate/tenant policy, or safety
against a host that directly supplies an unredacted event to the exporter.
Those are explicitly separate contracts in ADR-059.

## Executed evidence

- Focused event/server tests: `22 passed in 4.46s`.
- Final tracked regression, excluding the five user-owned untracked Doctrine
  tests: `1279 passed, 1 skipped in 212.83s (0:03:32)`.
- Changed-source Black: `4 files would be left unchanged`.
- Changed-source Ruff: `All checks passed!`.
- Changed-boundary mypy: `Success: no issues found in 1 source file`.
- `compileall exit: 0`.
- `git diff --check exit: 0`.

## Verdict

- [x] Pass (0 BLOCKER, MAJOR, or unresolved MINOR findings)
- [ ] Return to build

The code and contract are clean for this bounded local/remote event-export
slice. The separate security gate retains the environment-level dependency
audit veto recorded in the QA artifact; this review does not waive it.
