# Slice 196 brief - bounded provider failover

**Date:** 2026-08-29
**Class:** L
**Role:** Chief Architect / ML / Backend / Security / Interop / QA / Release
**Status:** implemented; QA/security passed for the scoped local change

## Objective

Close the local provider-resilience gap visible in the parity ledger. A host
should be able to opt into deterministic request-time failover across already
configured, capability-compatible LLM providers without changing the default
single-provider behavior or implying distributed routing.

## In scope

- a public `FallbackLLMProvider` over existing `LLMProvider` instances;
- an additive `ProviderRouter.create(..., failover=True)` option;
- deterministic provider order inherited from `ProviderRouter.select()`;
- bounded provider count and exact retryable error-type validation;
- sync and async completion failover for classified transient errors;
- fail-fast behavior for caller/auth/validation errors and final typed errors;
- explicit rejection of failover creation when native streaming is required;
- usage accounting, exports, tests, API/README/parity/changelog documentation.

## Out of scope

- provider SDKs, model changes, credentials, or new dependencies;
- automatic failover by default, cross-request circuit state, health polling,
  load balancing, quotas, hosted routing, or distributed coordination;
- retrying a provider after a response has begun streaming;
- tool execution, side-effect replay, exactly-once behavior, or billing
  reconciliation across providers;
- cloud, publication, release-version changes, or website work.

## Acceptance criteria

1. The default router behavior remains unchanged; with `failover=True`, all
   configured compatible providers initialize in deterministic selection order
   and are bounded to at most eight attempts.
2. Sync and async completion calls advance only on the configured exact error
   types (`LLM_RATE_LIMITED`, `LLM_TIMEOUT`, `LLM_TRANSIENT_ERROR` by default),
   classify raised provider exceptions, and fail fast on non-retryable errors.
3. A successful response is returned unchanged, wrapper usage remains bounded,
   and an exhausted chain returns a typed final error with sanitized bounded
   attempt metadata.
4. `failover=True` with `ProviderRequirements(streaming=True)` returns a typed
   unsupported error before provider construction; native streaming remains a
   direct-provider concern.
5. The public surface is exported and documented with a runnable example;
   deterministic sync/async, failure, bounds, ordering, and no-new-dependency
   tests pass without changing hosted/distributed claims.
