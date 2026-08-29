# ADR-125: Least-privilege agent target policy on Principal

**Date:** 2026-08-28 · **Status:** proposed
**Deciders:** Chief Architect (local host-owned contract)

## Context

`RunServer` currently attaches one configured `Principal` to its bearer-token
boundary. Scope checks distinguish read, invoke, resume, cancel, and restore,
but an invoking principal is not restricted to a particular registered agent
or capability. Agent discovery also returns the complete registry to any
principal with `agent:read`.

## Decision

Add two optional exact allowlists to `Principal`: `allowed_agent_ids` and
`allowed_capabilities`. Empty tuples preserve the existing scope-only behavior.
Named agent routes check the agent ID after authentication/scope authorization
and before reading a request body. Capability routes validate the capability,
then check the allowlist before idempotency claims or registry routing. Agent
discovery filters descriptors by both allowlists so denied targets are not
advertised. Denials are bounded `403 FORBIDDEN` responses and do not call a
handler.

## Alternatives considered

| Option | Pros | Cons | Why not |
|--------|------|------|---------|
| Exact allowlists on the existing `Principal` (chosen) | Additive, deterministic, host-owned, easy to audit | Static policy; no token federation | Closes the immediate least-privilege gap without inventing an identity service |
| Per-agent callback policy | Dynamic and expressive | More callback timing/body semantics and failure modes | Defer until a host policy engine contract exists |
| Token-to-principal resolver | Supports multiple identities | Authentication/issuance and federation scope expansion | Explicitly outside this local control-plane slice |
| No target policy | No implementation cost | Any scoped invoker can reach every agent | Leaves least privilege incomplete |

## Consequences

- Positive: one host token can be narrowed to selected agents and capabilities;
  discovery and invocation follow the same policy.
- Negative / debt accepted: lists are static and only cover agent routes; they
  do not provide tenancy, identity federation, or body-level authorization.
- Invalidation triggers: multiple token identities, policy decisions based on
  request claims, or host-wide tenant isolation.
