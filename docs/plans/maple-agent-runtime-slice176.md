# Implementation Plan — Bounded remote human-input push delivery

**Brief:** [maple-agent-runtime-slice176](../briefs/maple-agent-runtime-slice176.md) · **Design/ADRs:** [ADR-121](../adr/121-remote-human-input-push-delivery.md) · **Class:** L

## Slices (ordered; each leaves the tree green)

| # | Slice | Role | Files touched | Proven by (tests) | Status |
|---|-------|------|---------------|-------------------|--------|
| 1 | Add strict notification parsing and one-shot stdlib HTTP sender | Backend / Interop / Security | `maple/autonomy/interactions.py`, interaction exports | Model round-trip, bounds, endpoint policy, timeout, response/error mapping | complete |
| 2 | Add authenticated receiver route and client operation | Backend / Interop / Security | `maple/autonomy/server.py`, server exports | Auth/scope, malformed/oversized body, callback success/failure, acknowledgement | complete |
| 3 | Prove store integration and compatibility | QA / Backend | interaction and server regression tests | Created/responded/continued delivery, state authority on failure, existing notifier compatibility | complete |
| 4 | Publish the contract in repository artifacts | Tech Writer / Release | README, API reference, parity ledger, changelog, release plan, QA/review | Documentation/static checks and clean package verification | complete |

## Threat sketch (required for Class L)

Assets touched: human prompts, input schemas, run and tool-call identifiers,
operator bearer token, and callback availability. Entry points / untrusted
inputs: configured sender endpoint, notification JSON, bearer token, callback
result, response body, and network timing. Worst plausible abuse: an attacker
with route access injects a forged prompt into an operator callback, or a
malicious/oversized notification consumes memory or leaks response data.
Mitigations are HTTPS for non-loopback sends, bearer/scope checks, strict
bounded parsing, metadata-only acknowledgement, no response values in the
notification, and no logging of tokens or full bodies.

## Risks & rollback points

- Risk: a lost HTTP response creates ambiguous delivery → mitigation: one
  attempt, typed error, explicit no-retry contract → rollback: remove the
  additive sender/route while retaining local notifier behavior.
- Risk: callback receives forged or future-shaped data → mitigation: parse
  identity/status/event invariants before callback invocation → rollback:
  disable the receiver callback configuration; persisted stores are unchanged.
- Risk: public surface grows without operator policy → mitigation: distinct
  `interaction:notify` scope and host-owned TLS/identity/queue policy →
  rollback: do not configure the route in production.

## Deviation log (append-only, as they happen)

- 2026-08-28: scope narrowed to human-input notifications; approval-specific
  notification records and durable distributed delivery remain deferred because
  they require separate state and consumer semantics.

## Status snapshot (update at session end / handoff)

Done (with evidence): implementation, regressions, public documentation, QA,
review, and clean archive packaging. · Next: continue the remaining P0 parity
gaps. · Blocked on: none.
