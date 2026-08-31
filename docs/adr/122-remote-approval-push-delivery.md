# ADR-122: Bounded remote approval push delivery

**Date:** 2026-08-28 · **Status:** accepted
**Deciders:** Chief Architect (additive, local-first contract)

## Context

Approval stores persist tool-call arguments and decisions, and the existing
authenticated server can list, inspect, and decide them. A remote operator
still needs to poll to discover new approvals. The human-input transport
provides a useful bounded shape, but approval notifications need a separate
scope and must never expose a recorded execution result.

## Decision

Add `ApprovalNotification`, `ApprovalNotifier`, and
`HttpApprovalNotifier`. In-memory and file approval stores accept an optional
notifier and invoke it after a newly persisted request or approval decision.
The authenticated `POST /v1/approvals/notifications` receiver requires the
distinct `approval:notify` scope, validates the complete notification before
the host callback, returns an `accepted` metadata-only acknowledgement, and
never persists or mutates an approval. The sender permits loopback HTTP,
requires HTTPS for non-loopback endpoints, uses finite bounds, and never
retries. `RunClient.publish_approval_notification()` validates the same
acknowledgement.

The notification includes bounded tool-call arguments because an operator
needs them to make an approval decision, but excludes `execution_result` and
does not add actor identity that the current approval model does not record.

## Alternatives considered

| Option | Pros | Cons | Why not |
|--------|------|------|---------|
| Separate typed approval push boundary (chosen) | Least-privilege scope and clear approval lifecycle; preserves store authority | One-shot delivery can be lost or duplicated by network ambiguity | - |
| Reuse human-input notification route | Less route code | Blurs authorization and payload contracts between two action types | Approval control deserves a distinct scope and schema |
| MAPLE-managed durable notification queue | Replay, retry, and consumer cursors | Requires distributed ownership, deduplication, retention, and identity contracts | Deferred to a separate distributed-delivery slice |

## Consequences

- Positive: operator hosts can receive approval requests and decisions across
  processes without polling or granting decision authority to the notifier.
- Negative/debt accepted: no durable delivery, retries, replay, deduplication,
  hosted identity, TLS termination, or exactly-once effect guarantee.
- Invalidation triggers: approval inbox replay, multiple consumers, durable
  delivery, actor audit identity, or hosted policy requirements reopen this
  ADR.
