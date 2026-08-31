# Review — MAPLE agent-runtime slice 33

## Scope

Wire the existing resource allocation and negotiation services into the MCP
adapter through explicit optional dependencies, with boundary validation and
fail-closed behavior when a host has not configured a service.

## Review findings

- `MCPAdapter` remains backward compatible for existing two-argument callers.
- `allocate` and `release` use the host-injected `ResourceManager`; release
  resolves the authoritative tracked allocation by ID.
- `negotiate` uses the host-injected `ResourceNegotiator` and runs its blocking
  request in the event loop's default executor.
- Invalid actions, malformed resource requests, missing IDs, unknown
  allocations, and missing services produce structured errors.
- README usage and ADR-023 document ownership, action shape, and failure
  semantics.

## Decision

Slice accepted as a bounded capability completion. Host services remain
explicitly injected; no global resource state or new dependency was added.
Publication, cloud deployment, and website work remain human-gated.
