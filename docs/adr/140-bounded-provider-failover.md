# ADR-140: Bounded provider failover

**Date:** 2026-08-29
**Status:** proposed
**Deciders:** Chief Architect

## Context

`ProviderRouter` already filters providers by declared capabilities and orders
them by priority/name, while `ModelRetryPolicy` can retry transient failures
against one provider. The parity ledger still lacks an explicit local
request-time fallback across configured providers. Adding implicit fallback
would alter latency, cost, model identity, and failure semantics, so the host
must opt in and the retry boundary must be narrow.

## Decision

Add `FallbackLLMProvider`, a bounded composition of initialized
`LLMProvider` instances, and an additive `failover=True` keyword to
`ProviderRouter.create(...)`. The router supplies instances in the existing
deterministic priority/name order. The wrapper attempts each provider at most
once per completion call, advances only for exact configured retryable error
types, classifies raised provider exceptions conservatively, and returns the
last typed error with bounded provider-attempt metadata when the chain is
exhausted. The default retryable set is the existing transient trio:
`LLM_RATE_LIMITED`, `LLM_TIMEOUT`, and `LLM_TRANSIENT_ERROR`.

Failover is completion-only. A router request that requires native streaming
with `failover=True` returns `PROVIDER_FAILOVER_STREAM_UNSUPPORTED` before
constructing providers. No circuit state, health worker, load balancing,
distributed identity, tool execution, or side-effect replay is introduced.

## Data flow and failure boundary

```text
requirements + configs
        │
        ▼
ProviderRouter.select() ── deterministic descriptors ──┐
        │                                               │
        └─ initialize configured providers (≤ 8) ───────▼
                                  FallbackLLMProvider.complete/complete_async
                                  │  provider result/exception
                                  ├─ non-retryable → typed error
                                  ├─ retryable → next provider
                                  └─ success → response + wrapper usage
```

Initialization failures are skipped as they are today; if no configured
provider initializes, the router returns `PROVIDER_SELECTION_FAILED`. A
provider completion exception is mapped to a bounded error type and does not
escape the wrapper. Cancellation is not swallowed. Provider calls are
sequential and have no shared mutable failover state, so the wrapper is safe
to use concurrently to the same extent as its child providers; child-provider
thread safety remains host-owned.

## Alternatives considered

| Option | Pros | Cons | Why not |
|--------|------|------|---------|
| Add bounded opt-in wrapper over the existing router (chosen) | Reuses capability ordering and error taxonomy; no dependency; removable | Completion-only; repeated requests can still reach a degraded provider | Best local contract with explicit semantics and small blast radius |
| Extend `ModelRetryPolicy` to switch providers | One policy object; agent integration | Couples model retries to provider construction and changes existing single-provider semantics | Keep same-provider retry and cross-provider failover separate |
| Add an external router/health service | Health-aware routing and fleet-wide policy | Requires tenancy, credentials, deployment, health authority, and distributed state | Deferred behind hosted-coordination contract |

## Consequences

- Positive: hosts can fail over a transient completion request without writing
  bespoke provider loops; ordering, bounds, and error types are testable.
- Negative / debt accepted: each attempted provider may incur latency or cost;
  the wrapper does not know whether a provider performed an external side
  effect, and it does not claim exactly-once semantics or native stream
  continuity.
- Invalidation triggers: a host requires health-aware routing, circuit
  breaking, weighted balancing, streaming continuation, cross-request policy,
  or distributed/provider-owned cost reconciliation.
