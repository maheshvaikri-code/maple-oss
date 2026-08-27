# Code Review — MAPLE Agent Runtime Slice 112 @ 74f8655

**Reviewer role:** Code Reviewer · **Date:** 2026-08-26
**Reviewed against:** [release brief](../briefs/maple-agent-runtime-release.md),
[release plan](../plans/maple-agent-runtime-release.md), and
[ADR-058](../adr/058-bounded-workflow-http-transport.md)
**Executed:** focused server/client tests, full tracked regression, Ruff,
Black, changed-boundary mypy, compile, and diff checks

## Findings

| # | Sev | Location | Finding | Suggested fix | Resolution |
|---|-----|----------|---------|---------------|------------|
| 1 | [MINOR] | `maple/autonomy/server.py` | The initial review pass identified that client request bodies needed an explicit byte bound and that authenticated non-loopback URLs needed an HTTPS guard. | Add `max_body_bytes`, reject oversized serialized payloads, reject control characters, and require HTTPS for authenticated non-loopback targets. | fixed in final feature commit `74f8655` and covered by `tests/autonomy/test_server.py` |

No BLOCKER or MAJOR findings remain.

## Scope check

The final diff matches Slice 112: a dependency-free workflow HTTP client,
optional server bearer authentication, public exports, bounded request/path/
response handling, tests, ADR, parity/API/README documentation, changelog, and
release-plan evidence. It does not add hosted service behavior, arbitrary
interface binding, TLS termination, token issuance, tenancy, retries, or
exactly-once side-effect claims.

The authorization gate runs before route dispatch, protects health and run
routes, uses constant-time token comparison, and fails closed. The client
never puts credentials in URLs, URL-encodes route identifiers, and normalizes
HTTP/transport/JSON/size failures into `Result` errors.

## Executed evidence

Focused result: `7 passed in 3.75s`.

Final committed-tree regression result:
`1276 passed, 1 skipped in 255.31s (0:04:15)`.

Changed-boundary mypy: `Success: no issues found in 3 source files`.
Changed-source Ruff: `All checks passed!`. Black left the final Python files
unchanged, compile returned `0`, and `git diff --check` returned `0`.

## Verdict

- [x] Pass (0 BLOCKER, MAJORs resolved)
- [ ] Return to build

The code and contract are clean for this bounded local/remote-client slice.
The separate security gate still has an environment-level dependency-audit
veto recorded in the QA artifact; that veto is not waived by this code review.
