# ADR-121: Bounded remote human-input push delivery

**Date:** 2026-08-28 · **Status:** accepted
**Deciders:** Chief Architect (human confirmation is not required for the
recorded additive, local-first default)

## Context

Human-input stores already persist requests before invoking a local host
notifier, which keeps the store authoritative but does not reach an operator
process across a transport boundary. The existing authenticated loopback
server already provides bounded interaction control and a dependency-free
client, so a small typed push seam can reuse those authentication and JSON
limits. Delivery can be ambiguous when a network response is lost; claiming
retry safety or exactly-once effects would be incorrect without a durable
queue and consumer identity.

## Decision

We will add an additive `HumanInputNotification` parser, an explicit
`HttpHumanInputNotifier` that performs one bounded POST, and an authenticated
`POST /v1/interactions/notifications` receiver backed by a host-owned
callback. The receiver requires the distinct `interaction:notify` scope,
validates the complete notification before invoking the callback, returns a
metadata-only acceptance acknowledgement, and never persists or mutates an
interaction. The sender allows loopback HTTP and requires HTTPS for
non-loopback endpoints, uses a finite timeout, and never retries. Existing
local notifier callbacks remain unchanged.

## Alternatives considered

| Option | Pros | Cons | Why not |
|--------|------|------|---------|
| Explicit one-shot HTTP sender plus typed receiver callback (chosen) | Small additive boundary; works across processes; reuses bearer auth and host-owned state; no runtime dependency | Delivery can be lost or duplicated by network ambiguity; host owns queue/retry policy | — |
| Reuse the generic event exporter/stream | Existing transport and redaction machinery; useful for observability | Does not provide a typed operator notification contract or receiver callback acknowledgement; event semantics are intentionally non-blocking | Human-input delivery needs a distinct action-facing contract |
| Durable MAPLE-managed notification queue | Could support replay, retry, and consumer cursors | Adds storage, ownership, leasing, deduplication, and hosted delivery policy before those contracts are specified | Deferred to a separate distributed-delivery design |

## Consequences

- Positive: a host can connect persisted human-input lifecycle changes to a
  remote operator boundary with least-privilege authorization and bounded
  failure behavior; local integrations remain source-compatible.
- Negative / debt accepted: one-shot delivery is not durable, retries are not
  automatic, approval notifications remain separate, and TLS/identity/
  tenancy are host responsibilities.
- Invalidation triggers: a requirement for replayable delivery, multiple
  consumers, cross-process deduplication, approval notification parity, or a
  hosted identity/queue service reopens this ADR.
