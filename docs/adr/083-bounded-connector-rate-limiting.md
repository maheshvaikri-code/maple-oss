# ADR-083: Bounded connector rate limiting

Status: Accepted for preview

Date: 2026-08-27

## Context

Document connectors are host-owned and may have provider-specific request
budgets. MAPLE's bounded ingestion loop needed an explicit local admission
seam so a host can cap fetches without adding an implicit sleep, retry, or
provider policy to the connector contract.

## Decision

Add `DocumentConnectorRateLimiter` with an `allow()` method that returns
`Result.ok(None)` for one admitted fetch or a typed denial. The reference
`InMemoryDocumentConnectorRateLimiter` implements a thread-safe trailing
window with bounded `max_calls` and `window_seconds` settings. It uses an
injectable monotonic clock for deterministic tests, rejects clock regressions,
and reports a bounded `retry_after_seconds` hint when its window is full.

`ingest_documents(...)` accepts an optional rate limiter and calls it exactly
once immediately before each connector fetch. Denials and malformed/raising
callbacks fail closed before connector activity; callback details are not
propagated. The helper does not sleep, retry, queue, or schedule a later
fetch. A host may implement the protocol for a provider or distributed
budget, but that policy and its durability remain outside MAPLE.

## Alternatives considered

| Alternative | Decision |
| --- | --- |
| Sleep until a local budget is available | Rejected: hidden blocking and lifecycle ownership do not belong in ingestion. |
| Retry a denied fetch automatically | Rejected: it changes run duration and retry semantics without host consent. |
| Make rate limits connector-specific inside MAPLE | Rejected: provider quotas, credentials, and remote coordination are host-owned. |
| Use a process-global limiter | Rejected: limits must be explicitly scoped to the connector instance or host policy. |

## Security and failure boundaries

- The reference limiter stores only bounded timestamps and no connector
  payload, credentials, response, or document data.
- The time window and call count are finite; injected clock failures and
  backwards movement fail closed.
- Rate-limit callback failures are sanitized before returning to callers.
- No network call, retry, sleep, queue, managed service, distributed
  coordination, or exactly-once request claim is introduced.
