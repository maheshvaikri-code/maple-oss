# ADR-110: Authenticated Handoff Result Delivery

**Date:** 2026-08-28
**Status:** accepted
**Deciders:** Chief Architect

## Context

The local `HandoffStore` already validates and retains a bounded successful
result on a completed handoff. The existing authenticated transport deliberately
omits that result from metadata inspection, so a target process cannot deliver
its output to a source process through the transport. Sending task or context
contents would widen the trust boundary and change the digest-only contract.

## Decision

We will extend the existing authenticated handoff completion operation with an
optional bounded JSON-object `result`, delegated to the store's existing
`complete(..., result=...)` contract. We will add a separate
`GET /v1/handoffs/<handoff_id>/result` route and `RunClient.get_handoff_result()`
operation. The result route requires the host-configured `handoff:result`
principal scope, returns only a completed record that has a result, and keeps
ordinary `handoff:read` inspection result-redacted. The server remains
loopback-first and bearer-authenticated, the store remains authoritative for
ownership and terminal state, and the client performs no automatic retries.

## Data flow and failure modes

```text
target result + target identity
  -> authenticated POST /handoffs/<id>/complete
  -> bounded request decode
  -> HandoffStore.complete(..., result=...)
  -> atomic completed record
  -> authenticated GET /handoffs/<id>/result
  -> handoff:result scope + bounded response
  -> source receives result
```

- A missing or null result preserves legacy result-less completion.
- A non-object, non-JSON, oversized, or invalid result is rejected before the
  store transition; the record remains unchanged.
- Missing handoffs return `HANDOFF_NOT_FOUND`; existing but unavailable
  results return `HANDOFF_RESULT_UNAVAILABLE`; insufficient scope returns
  `FORBIDDEN`.
- The route does not transfer raw task/context content, consume the result,
  retry transport calls, or make an exactly-once external-effect claim.

## Alternatives considered

| Option | Pros | Cons | Why not |
|---|---|---|---|
| Separate scoped result pull over the existing transport (chosen) | Preserves digest-only inspection, reuses store validation, and gives the source an explicit bounded read | Source must poll or coordinate its own wake-up | Smallest additive delivery boundary with clear authorization |
| Include `result` in every handoff inspection response | One request for consumers | Leaks result to every metadata reader and breaks the existing redaction contract | Violates least-privilege inspection |
| Push results through a broker or callback | Lower polling latency | Adds broker ownership, retries, delivery acknowledgements, and new failure semantics | Deferred until a delivery protocol is specified |
| Copy raw result into task/context transport | One payload channel | Expands sensitive-data exposure and couples result to task delivery | Rejected because task/context remain digest-only |

## Consequences

- Positive: authenticated remote targets can submit bounded results and
  authorized sources can retrieve them without an out-of-band result channel.
- Negative / debt accepted: result retrieval is pull-based and host-scoped;
  bearer authentication is not an agent identity provider, and network retry
  policy remains caller-owned.
- Invalidation triggers: a reviewed per-agent identity model, push/ack
  delivery requirement, result consumption/retention requirement, or
  exactly-once side-effect contract.
