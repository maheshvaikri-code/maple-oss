# Code Review — MAPLE Agent Runtime Slice 114 @ 6771fa3

**Reviewer role:** Code Reviewer · **Date:** 2026-08-26
**Reviewed against:** [release brief](../briefs/maple-agent-runtime-release.md),
[release plan](../plans/maple-agent-runtime-release.md), and
[ADR-060](../adr/060-bounded-authenticated-human-input-transport.md)
**Review scope:** feature commit `8ec8357`, authentication fix `d41c65a`, and
release documentation commit `6771fa3`

## Findings

| # | Sev | Location | Finding | Resolution |
|---|-----|----------|---------|------------|
| 1 | [MAJOR risk if misconfigured] | `RunServer(human_input_store=...)` | The initial transport allowed a human-input store without a bearer token, which would expose prompts and permit mutations to any local caller. | Fixed in `d41c65a`: configuring `human_input_store` without `auth_token` raises `ValueError`; regression coverage added. |

No BLOCKER, MAJOR, or unresolved MINOR findings remain.

## Scope check

The final slice extends the existing bounded loopback workflow server/client
with optional authenticated human-input operations: pending listing,
inspection, response, rejection, bounded continuation, and one-time consume.
The configured `HumanInputStore` remains authoritative for JSON Schema
validation, actor authorization, durable leases, notifications, and state
transitions. The transport reuses existing request/response/path bounds and
typed error envelopes.

The slice does not add a hosted operator service, non-loopback binding, TLS
termination, token issuance, identity federation, tenancy, rate limiting,
automatic run scheduling/resume, or exactly-once side-effect semantics.

## Executed evidence

- Focused server/interaction tests: `19 passed in 5.17s`.
- Final tracked regression, excluding the five user-owned untracked Doctrine
  tests: `1283 passed, 1 skipped in 275.08s (0:04:35)`.
- Changed-source Black: `2 files left unchanged`.
- Changed-source Ruff: `All checks passed!`.
- Changed-boundary mypy: `Success: no issues found in 1 source file`.
- Compile and `git diff --check`: exit `0`.

## Verdict

- [x] Pass (0 BLOCKER, MAJOR, or unresolved MINOR findings)
- [ ] Return to build

The hardened code and contract are clean for this bounded local interaction
transport slice. The separate security gate retains the environment-level
dependency audit veto recorded in the QA artifact; this review does not waive
it.
