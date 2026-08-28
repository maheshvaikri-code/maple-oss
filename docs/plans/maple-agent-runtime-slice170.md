# Implementation Plan - Bounded Agent Capability Discovery and Routing

**Brief:** [Slice170 brief](../briefs/maple-agent-runtime-slice170.md)
**Design/ADR:** [ADR-115](../adr/115-bounded-agent-capability-routing.md)
**Class:** L

## Slices

| # | Slice | Role | Files touched | Proven by (tests) | Status |
|---|---|---|---|---|---|
| 1 | Add bounded descriptors, capability registration, deterministic registry routing, and native adapter metadata | Backend / Interop / Security | `maple/autonomy/server.py`, `maple/autonomy/agent_transport.py`, exports | Registration bounds, sorted detached descriptors, exact matching, selected identity, legacy compatibility | pending |
| 2 | Add authenticated listing/routing HTTP routes and raw/typed client methods | Backend / Interop / QA | `maple/autonomy/server.py`, server/client regressions | Scope enforcement, missing registry, no match, route integration, typed normalization | pending |
| 3 | Update public contracts and close review/QA/security/package gates | Tech Writer / Code Reviewer / QA / Release | README, API reference, parity ledger, changelog, `docs/reviews/`, `docs/qa/`, release plan | Focused/tracked tests, static/security checks, clean archive, install/import | pending |

## Risks and rollback points

- Risk: a capability route silently becomes load balancing -> mitigation: exact
  lexicographic selection and explicit no-scheduler documentation -> rollback:
  remove only the route and metadata surface; named routes remain.
- Risk: discovery leaks private host state -> mitigation: descriptors contain
  only bounded public IDs and labels, with `agent:read` authorization ->
  rollback: disable the listing route while retaining direct invocation.
- Risk: a selected response is attributed to the wrong agent -> mitigation:
  validate server-side and typed-client-side identity against the returned
  envelope -> rollback: retain raw named-agent calls until the route is fixed.

## Deviation log (append-only, as they happen)

- None.

## Status snapshot

Design recorded; implementation and gates pending. Publication authorization,
cloud actions, and website changes remain outside this plan.
