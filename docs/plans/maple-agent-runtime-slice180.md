# Implementation Plan - Least-privilege agent target policy

**Brief:** [maple-agent-runtime-slice180](../briefs/maple-agent-runtime-slice180.md) · **Design/ADR:** [ADR-125](../adr/125-principal-agent-target-policy.md) · **Class:** M

## Slices

| # | Slice | Role | Files touched | Proven by (tests) | Status |
|---|-------|------|---------------|-------------------|--------|
| 1 | Extend `Principal` with bounded exact allowlists | Backend / Security | `maple/autonomy/server.py`, exports | Constructor validation and allow semantics | complete: `8b97e52` |
| 2 | Enforce policy on discovery and agent routes | Backend / Security | `maple/autonomy/server.py` | No target on named/capability denial; filtered descriptors | complete: `8b97e52` |
| 3 | Regression, public contract, and package evidence | QA / Tech Writer / Release | server tests, README/API/parity/changelog, QA/review/release artifacts | Full/static/clean archive/package checks | complete: `abb21c9` |

## Threat sketch

Assets touched: agent metadata, invocation routing, handler side effects, and
principal policy. Entry points: malformed allowlists, denied named IDs, denied
capabilities, discovery leakage, and request bodies. Worst plausible abuse:
overbroad token access or target metadata disclosure.

Mitigations: bounded exact validation, pre-body named checks, pre-routing
capability checks, filtered discovery, typed `403`, no payload logging, and no
new authentication mechanism.

## Risks & rollback points

- Risk: existing callers pass non-tuple list-like policy values → mitigation:
  fail closed with constructor validation; rollback: omit the new fields.
- Risk: policy is applied inconsistently across agent routes → mitigation:
  central dispatch target check plus capability-route regression tests; rollback:
  remove enforcement while retaining scope-only behavior.

## Deviation log

- None.

## Status snapshot

Done (with evidence): design brief/ADR, bounded target policy, server
regressions, public contract, and clean archive package gate. Next: continue
the next explicitly scoped parity gap. Blocked on: none.
