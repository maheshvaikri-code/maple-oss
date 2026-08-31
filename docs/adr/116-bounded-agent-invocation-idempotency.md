# ADR-116: Bounded Agent Invocation Idempotency

**Date:** 2026-08-28
**Status:** accepted
**Deciders:** Chief Architect, Backend Engineer, Interop, Security Reviewer

## Context

The authenticated agent control plane currently executes a named or
capability-routed handler for every accepted request. A caller that retries
after a transport timeout cannot tell the host that the second request is the
same logical invocation, so a handler may execute twice. The repository
already has bounded claim/complete/abort patterns for event deduplication and a
shared file fencing lease, but no equivalent request-boundary policy for agent
invocations.

## Decision

Add an optional `idempotency_key` to named-agent and capability-routed
invocations. When a host configures an `AgentInvocationDeduplicationStore`,
the server canonicalizes the validated target and request fields, computes a
SHA-256 request digest, and claims `(target, idempotency_key)` before invoking
the existing `AgentRegistry` path. A matching completed claim replays its
detached bounded HTTP response; a matching pending claim returns
`AGENT_INVOCATION_IN_PROGRESS`; a different digest returns
`AGENT_INVOCATION_CONFLICT`. The first accepted invocation completes the claim
only after the existing run normalizer produces a valid response. Errors are
stored as bounded error envelopes so a retry cannot unexpectedly re-execute a
handler that already returned an error. Storage failures are surfaced and the
handler result is never silently retried.

Provide thread-safe `InMemoryAgentInvocationDeduplicationStore` and atomic,
fenced `FileAgentInvocationDeduplicationStore` implementations with finite
entry/TTL/byte limits. The store retains only the target, key, digest, expiry,
and normalized response envelope; it never stores the raw task or context.
Expose the protocol, response value, constants, and both implementations from
the public autonomy and package roots. The client adds the optional field to
raw and typed named/capability methods while preserving absent-key wire
compatibility.

This is a bounded retry-deduplication guard, not a distributed exactly-once
protocol. Resume/cancel operations, push delivery, identity federation,
automatic retries, failover, and multi-node shared coordination remain
separate contracts.

## Data flow and failure modes

```text
client optional key + request
  -> bearer authentication + agent:invoke scope
  -> bounded field normalization
  -> canonical digest
  -> claim (memory or fenced file store)
       -> completed response: detached replay
       -> pending claim: conflict, no handler call
       -> new claim: continue
  -> existing named/capability registry invocation
  -> existing AgentRun/error normalization
  -> complete stored response
  -> bounded HTTP response
```

- Invalid key or request is a caller error and does not invoke a handler.
- Missing store configuration when a key is supplied is an unavailable
  idempotency boundary; the keyed request fails closed rather than silently
  running without deduplication.
- A same-key different-digest request is a conflict and leaves the stored
  record unchanged.
- A claim race returns a typed in-progress conflict; no wait or retry occurs
  inside the server.
- A malformed or oversized persisted file fails closed without mutation.
- A completion write failure is reported as a storage error. The handler is
  not called again, because external side effects may already have occurred.
- TTL expiry and completed-record capacity eviction are explicit limits;
  after eviction, a later request may execute again. This is documented and
  is not an exactly-once guarantee.

## Alternatives considered

| Option | Pros | Cons | Why not |
|---|---|---|---|
| Bounded host-owned claim/complete stores (chosen) | Reuses proven local patterns; supports concurrent suppression and restart replay; keeps raw handler boundary unchanged | Expiry, eviction, and crash windows remain; no fleet-wide coordination | Best incremental retry-safety contract without claiming distributed semantics |
| Use `run_id` as implicit idempotency key | No new field or store API | Existing callers may omit IDs; same run ID can still be re-executed; cannot distinguish request payload conflicts | Conflates execution identity with caller request identity |
| Always execute and let callers deduplicate results | Minimal server state | Duplicate handler side effects remain possible; retries are not safer | Does not address the reported correctness boundary |
| Add a distributed transactional idempotency service | Stronger multi-node coordination | Adds a service/dependency, identity policy, recovery protocol, and exactly-once expectations | Out of scope for the local-first library and requires separate host approval |

## Consequences

- Positive: callers can safely retry within a bounded host-owned window; the
  same request gets a stable response, and concurrent duplicates are stopped
  before handler execution.
- Negative / debt accepted: a retained response is not a replay of handler
  state; TTL/eviction and crash windows can permit re-execution, and a keyed
  request requires an explicitly configured store.
- Invalidation triggers: multi-node shared ownership, caller/tenant identity
  binding, push acknowledgements, automatic retry orchestration, or a
  requirement for exactly-once external effects reopens this decision.
