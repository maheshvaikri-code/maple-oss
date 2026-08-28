# ADR-089: Async Completion Capability Routing

## Status

Accepted for preview release readiness.

## Context

MAPLE providers expose a common asynchronous completion method. Providers that
inherit the base implementation may still delegate to a synchronous method,
which is a compatibility path but is not a non-blocking guarantee. Async agent
callers need a way to reject such a descriptor when a native async client is a
requirement.

## Decision

Add `async_completion` to `ProviderCapabilities` and `ProviderRequirements`.
The router matches `ProviderRequirements(async_completion=True)` only against
descriptors that explicitly declare `ProviderCapabilities(async_completion=True)`.

The router remains declaration-driven. It does not introspect methods, probe
SDK objects, or infer non-blocking behavior. The capability is therefore an
explicit provider/model-family contract that adapters and hosts must declare
truthfully.

## Boundaries

This decision does not change provider construction, add dependencies, add
retries, or make an undeclared provider asynchronous. It does not claim that
native async completion is available for every provider or model. The existing
base-provider synchronous fallback remains available when the requirement is
not requested.

## Evidence

Offline capability-router coverage verifies that an async requirement selects
only the explicitly declared descriptor and excludes a provider that exposes
only the compatibility path. Full release evidence is recorded in the slice
144 QA and review records.
