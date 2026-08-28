# Implementation Plan - Bounded remote approval push delivery

**Brief:** [maple-agent-runtime-slice177](../briefs/maple-agent-runtime-slice177.md) · **Design/ADR:** [ADR-122](../adr/122-remote-approval-push-delivery.md) · **Class:** L

## Slices

| # | Slice | Role | Files touched | Proven by (tests) | Status |
|---|-------|------|---------------|-------------------|--------|
| 1 | Add strict approval notification model and local notifier hooks | Backend / Security | `maple/autonomy/approval.py`, approval exports | Round-trip, event/status invariants, create/decide persistence and failure behavior | complete |
| 2 | Add one-shot HTTP sender and authenticated receiver/client route | Backend / Interop / Security | `maple/autonomy/approval.py`, `maple/autonomy/server.py` | Auth/scope, bounds, callback ordering, acknowledgement and failure mapping | complete |
| 3 | Prove compatibility and adversarial behavior | QA / Backend | approval and remote notification tests | Existing lifecycle/lease tests plus malformed, oversized, unauthorized, and no-mutation cases | complete |
| 4 | Publish public contract and package evidence | Tech Writer / Release | README, API/parity/changelog, QA/review/release artifacts | Static checks, full suite, clean archive and isolated package smoke | complete |

## Threat sketch

Assets: tool-call names, bounded approval arguments, decisions, bearer token,
and callback availability. Entry points: notification JSON, endpoint URL,
response body, bearer token, callback result, and network timing. Worst
plausible abuse: unauthorized injection of a forged approval request, leakage
of execution output, or memory exhaustion through oversized input.

Mitigations: distinct bearer/scope authorization, strict bounded parsing,
HTTPS off loopback, metadata-only acknowledgement, no execution-result field,
bounded response handling, no body/token logging, and no retry or hidden
mutation. Approval stores remain the source of truth.

## Rollback

Disable the optional notifier and receiver callback configuration, or remove
the additive sender/route in a patch release. Existing local approval stores,
leases, and decision semantics remain intact.

## Status

Done with evidence: implementation, regressions, public documentation, QA,
review, and clean archive packaging. Next: continue the remaining P0 parity
gaps. No external state, publication, cloud action, or website update is in
scope.
