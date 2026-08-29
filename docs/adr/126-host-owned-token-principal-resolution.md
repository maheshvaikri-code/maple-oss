# ADR-126: Host-owned bearer token-to-principal resolution

**Date:** 2026-08-28 - **Status:** proposed
**Deciders:** Chief Architect (local host-owned contract)

## Context

RunServer currently authenticates one exact bearer token and, optionally,
attaches one static Principal to every authenticated request. Slice 180 added
least-privilege agent and capability allowlists to that principal, but distinct
tokens cannot select distinct scope or target policies.

## Decision

Add an optional synchronous auth_principal_resolver callback to RunServer.
When configured, the server extracts and bounds the bearer token, invokes the
callback once before scope or route processing, and accepts only a Principal
or Result.ok(Principal). Result.err, None, wrong types, malformed bearer
headers, and callback exceptions all return the same generic 401 UNAUTHORIZED
response with WWW-Authenticate: Bearer; callback details and credentials are
never serialized or logged.

auth_principal_resolver is mutually exclusive with static auth_token and
auth_principal. Existing static-token behavior remains unchanged. All existing
route and agent-target authorization reads the request-selected principal, so
resolver-backed callers inherit scopes and exact target allowlists without a
second policy path.

## Alternatives considered

| Option | Pros | Cons | Why not |
|--------|------|------|---------|
| Host-owned resolver callback (chosen) | Additive, testable, supports distinct local principals | Host owns validation and callback lifecycle | Closes the immediate gap without inventing an identity provider |
| Accept a token map in RunServer | Simple local lookup | Stores secrets in server configuration and has no host validation seam | A callback keeps credential ownership with the host |
| Parse JWT/JWKS in MAPLE | Familiar federation model | Adds key rotation, clock, algorithm, network, and dependency/security scope | Explicitly outside the local runtime contract |
| Keep one static principal | No implementation cost | Cannot express per-token least privilege | Leaves token-to-principal parity gap open |

## Consequences

- Positive: distinct bearer tokens can receive distinct scope and agent-target
  policies while sharing one bounded local server.
- Negative / debt accepted: no issuer validation, caching, refresh, revocation,
  tenancy, or async identity integration is provided.
- Invalidation triggers: a requirement for built-in federation, token claims,
  tenant isolation, remote policy evaluation, or asynchronous identity calls.
