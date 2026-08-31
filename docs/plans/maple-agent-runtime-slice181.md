# Implementation Plan - Host-owned token-to-principal resolution

**Brief:** maple-agent-runtime-slice181 (docs/briefs/maple-agent-runtime-slice181.md) - **Design/ADR:** ADR-126 (docs/adr/126-host-owned-token-principal-resolution.md) - **Class:** M

## Slices

| # | Slice | Role | Files touched | Proven by (tests) | Status |
|---|-------|------|---------------|-------------------|--------|
| 1 | Add resolver configuration and request principal selection | Backend / Security | maple/autonomy/server.py, exports if needed | Static/resolver exclusivity and per-request selection | complete: dcc5001 |
| 2 | Enforce fail-closed resolver and compatibility behavior | Backend / Security / QA | maple/autonomy/server.py, server tests | Generic 401, no body/callback detail, static regression | complete: 85fde19; focused 54 passed; full workspace 1724 passed, 1 skipped |
| 3 | Public contract, parity, and package evidence | Tech Writer / Release | README/API/parity/changelog, QA/review/release artifacts | Full/static/clean archive/package checks | complete: af37173 |

## Threat sketch

Assets touched: bearer credentials, principal scopes, agent target policy, and
protected route side effects. Entry points: malformed headers, resolver
exceptions, invalid callback results, token disclosure, and mixed static/
resolver configuration. Worst plausible abuse: a resolver bug broadens access or
leaks a credential.

Mitigations: bounded bearer extraction, callback-before-body processing,
generic fail-closed 401, strict Principal result validation, mutual
configuration validation, no credential logging, and reuse of the existing
authorization path.

## Risks & rollback points

- Risk: a callback performs slow or unsafe work on request threads - mitigation:
  synchronous host-owned contract is explicit and bounded only at token input;
  rollback: remove the resolver option and retain static authentication.
- Risk: one route accidentally reads the static principal - mitigation: central
  request-principal field plus resolver-backed scope/target tests; rollback:
  disable resolver mode until every protected path uses the selected principal.

## Deviation log

- None.

## Status snapshot

Done (with evidence): design brief/ADR, resolver implementation, per-request
principal selection, fail-closed regressions, public contract, static/full
validation, and clean archive package gate. Next: continue the next explicitly
scoped parity gap. Blocked on: none.
