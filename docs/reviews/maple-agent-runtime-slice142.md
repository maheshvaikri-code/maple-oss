# MAPLE Agent Runtime Slice 142 Review

Date: 2026-08-28

Scope reviewed: `Principal`, route-scope mapping, `RunServer` authorization
ordering, exports, server regressions, ADR-087, API/README/parity
documentation, changelog, and release-plan closure.

## Findings

- Principal IDs and scopes are bounded and immutable; exact and family scope
  matching is deterministic, and malformed policies fail at configuration.
- Bearer authentication remains constant-time. Scope authorization executes
  after path validation but before request-body parsing, so denied callers do
  not consume route payloads.
- Known control routes have explicit least-privilege scope names for health,
  workflows, agents, approvals, human input, handoffs, and events. Missing
  permission is a sanitized `403`.
- The no-principal compatibility path preserves the existing single-token
  behavior; the implementation does not silently turn a token into a hosted
  identity or claim resource/tenant authorization.
- The slice adds no dependency, network call, token issuance, TLS behavior,
  retry, scheduling, body retention, or exactly-once side-effect guarantee.

## Disposition

Author-side review: no blocking finding for this slice. A fresh independent
verifier session was not available in this environment, so this record is not
represented as independent verifier approval. Multiple bearer tokens, dynamic
identity resolution, tenant/resource policy, delegated child-run identity,
remote policy evaluation, and hosted audit remain separate boundaries.
