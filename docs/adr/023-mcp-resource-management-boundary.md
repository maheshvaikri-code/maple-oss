# ADR-023: Inject resource services at the MCP boundary

**Date:** 2026-08-25  
**Status:** accepted  
**Deciders:** Chief Architect

## Context

MAPLE advertises `maple_resource_management` in its MCP server descriptor, but
the adapter has no host-owned resource service to call. The safe fallback is a
structured fail-closed error, but leaving the capability permanently
unavailable makes the advertised MCP surface incomplete. Resource allocation
is already implemented by `ResourceManager`, while cross-agent negotiation is
implemented by `ResourceNegotiator`; the adapter should compose those existing
contracts without creating a second resource model or a global singleton.

The MCP boundary receives untrusted JSON-like dictionaries, so action,
resource, and allocation identifiers must be validated before invoking the
resource services. The adapter is asynchronous, while the resource services
are synchronous; negotiation must therefore be moved off the event loop and
bounded by its existing timeout contract.

## Decision

We will add optional, keyword-only `ResourceManager` and
`ResourceNegotiator` dependencies to `MCPAdapter`. `allocate` and `release`
operate only when a manager is injected; `negotiate` operates only when a
negotiator is injected and requires `agent_id`. Missing services continue to
return the existing structured `RESOURCE_MANAGEMENT_UNAVAILABLE` error.
Requests are converted through `ResourceRequest.from_dict`, successful
allocations return the existing `ResourceAllocation.to_dict()` shape, and
invalid actions or arguments return actionable structured caller errors.
Synchronous negotiation runs in the event loop's default executor. No global
resource state, new dependency, or host-specific callback protocol is added.

## Alternatives considered

| Option | Pros | Cons | Why not |
|--------|------|------|---------|
| Inject existing manager/negotiator (chosen) | Reuses tested contracts; backward compatible; explicit ownership; easy to test | Adds two optional constructor dependencies; synchronous negotiation needs an executor | — |
| Put resource services in `mcp_config` | Fewer constructor parameters | Hides typed dependencies in an untrusted/config dictionary; weaker discoverability and typing | Rejected at the public boundary |
| Keep fail-closed permanently | No API change or concurrency concerns | Advertised resource tool can never work | Rejected because the capability already exists internally |
| Add a new MCP-specific resource abstraction | Could tailor every action to MCP | Duplicates allocation semantics and creates another compatibility surface | Rejected in favor of composition |

## Consequences

- Positive: MCP hosts can opt into real local allocation, release, and
  cross-agent negotiation without changing existing callers.
- Positive: unconfigured adapters remain safe and explicit rather than
  silently pretending to manage resources.
- Negative / debt accepted: `ResourceManager` still exposes legacy dictionary
  contracts internally; a future typed boundary can improve that separately.
- Invalidation triggers: a versioned MCP resource schema, asynchronous native
  resource services, or a host lifecycle model that requires leases instead of
  allocation IDs would reopen this decision.
