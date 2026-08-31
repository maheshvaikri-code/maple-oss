# Project/Task Brief - Host-owned token-to-principal resolution

**Date:** 2026-08-28 - **Class:** M (additive authenticated server boundary) - **Requested by:** human

## Problem

The local control plane currently supports one static bearer token and one
host-configured Principal. That is sufficient for a single local caller but
cannot apply the existing scope and target policy to distinct bearer tokens.
The parity ledger therefore still lacks a narrow token-to-principal seam.

## Scope

- In: an optional synchronous RunServer principal resolver callback.
- In: validated bearer extraction, per-request principal selection, and use of
  the selected principal for all existing scope and agent-target checks.
- In: generic fail-closed 401 handling for resolver rejection, exceptions,
  invalid results, and malformed bearer credentials.
- In: preserve static auth_token/auth_principal compatibility and reject
  ambiguous configurations.
- **Non-goals:** token issuance, JWT parsing, JWKS/OAuth discovery, revocation
  storage, async resolvers, tenant isolation, remote identity federation,
  caching, refresh, or policy decisions from request bodies.

## Acceptance criteria

1. A host can configure auth_principal_resolver instead of a static auth_token;
   the callback receives only a validated bearer token and may return a
   Principal or Result.ok(Principal).
2. Every authenticated request resolves its principal before scope, target, or
   route handling; resolver failures, exceptions, invalid values, and
   Result.err become bounded generic 401 responses with no token or callback
   detail.
3. Existing static-token behavior remains unchanged, and resolver/static
   configurations cannot be combined ambiguously.
4. Existing stores and protected routes accept resolver-backed authentication;
   the selected principal applies to scope, discovery, and agent-target policy.
5. Public API, parity, changelog, review, QA, and release-plan evidence are
   updated; no publication, cloud, registry, or website action occurs.

## Constraints

Stdlib runtime and existing Principal/Result surfaces; additive API; bounded
bearer values; synchronous host callback; fail closed; no new dependency; no
raw credentials in errors or logs; no external identity calls.

## Assumptions

- The host owns token validation, expiry, revocation, and any identity
  federation behind the callback.
- The callback is invoked once per request and must be thread-safe.
- A resolver-backed server is authenticated; unauthenticated mode remains
  available only when neither static token nor resolver is configured.

**Human confirmed:** no - additive host-owned authentication seam recorded for
review
