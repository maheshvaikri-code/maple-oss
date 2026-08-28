# ADR-087: Bounded principal scopes for the local control plane

Status: Accepted for preview

Date: 2026-08-27

## Context

MAPLE's loopback `RunServer` already supports one optional bearer token. That
authenticates transport access but left every authenticated route equivalent,
which was too broad for hosts exposing workflow, approval, event, or agent
control through one local process.

## Decision

Add the immutable `Principal` contract with a bounded principal ID and 1-64
scope names. A scope is exact (`workflow:read`), a family wildcard
(`workflow:*`), or the legacy all-route wildcard (`*`). `RunServer` accepts an
optional `auth_principal` only alongside `auth_token`; known routes map to
scopes and reject missing permissions with `403` before request bodies are
read.

The scope map is:

| Route family | Scopes |
| --- | --- |
| Health | `health:read` |
| Workflows | `workflow:read`, `workflow:invoke` |
| Agents | `agent:read`, `agent:invoke`, `agent:resume`, `agent:cancel` |
| Approvals | `approval:read`, `approval:decide` |
| Human input | `interaction:read`, `interaction:write`, `interaction:consume` |
| Handoffs | `handoff:read`, `handoff:write` |
| Events | `event:read`, `event:publish` |

When no principal is configured, existing authenticated servers retain their
legacy wildcard behavior. When no bearer token is configured, the server stays
the existing unauthenticated local transport and no scope policy applies.

## Alternatives considered

| Alternative | Decision |
| --- | --- |
| Add a second token per route | Deferred: token issuance and multi-principal mapping require a host identity service. |
| Infer permissions from URL agent/workflow IDs | Rejected: identifiers are not authorization policy and can create confused-deputy paths. |
| Authorize after reading the request body | Rejected: rejected callers should not consume bounded input or trigger body parsing side effects. |
| Treat bearer authentication as authorization | Rejected: authentication alone cannot express least privilege. |

## Security and failure boundaries

- Existing constant-time bearer-token comparison remains the authentication
  boundary.
- Scope names, principal IDs, route paths, and rejected request bodies remain
  bounded; missing scopes return a sanitized `403`.
- The principal is host-configured and immutable; MAPLE does not issue,
  rotate, introspect, or federate identities.
- This contract does not provide TLS, tenancy, per-agent delegation identity,
  notification delivery, remote scheduling, or exactly-once effects.

## Invalidation triggers

Reopen this decision if hosts need multiple bearer tokens, dynamic identity
resolution, tenant/resource-level authorization, remote policy evaluation,
delegated child-run identity, or hosted audit guarantees. Those changes need a
separate identity and policy contract.
