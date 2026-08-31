# Project/Task Brief - Least-privilege agent target policy

**Date:** 2026-08-28 · **Class:** M (additive Principal policy) · **Requested by:** human

## Problem

The local control plane already binds one host-configured `Principal` to a
bearer token and enforces route scopes. A principal with `agent:invoke` can
currently invoke every registered agent and inspect every agent descriptor.
That is broader than the least-privilege policy needed by multi-agent hosts.

## Scope

- In: bounded exact `allowed_agent_ids` and `allowed_capabilities` allowlists
  on `Principal`.
- In: filter agent discovery, deny named-agent routes before request bodies are
  read, and deny capability routes before routing or idempotency claims.
- In: preserve empty-allowlist backwards compatibility and typed `403`
  failures without target invocation.
- **Non-goals:** token issuance, identity federation, token-to-principal
  resolution, tenant isolation, workflow/handoff policy, wildcard capability
  rules, or distributed authorization.

## Acceptance criteria

1. A principal can be restricted to exact agent IDs and/or exact capability
   labels with bounded constructor validation.
2. Restricted discovery returns only permitted agent descriptors; named-agent
   denial happens before the request body is read; capability denial happens
   before registry routing and invocation idempotency claims.
3. Empty allowlists preserve existing scope-only behavior, and all existing
   authentication/scope contracts remain compatible.
4. Denials expose only bounded policy metadata, never request payloads or
   credentials, and target handlers are not called.
5. Public API, parity, changelog, review, QA, and release-plan evidence are
   updated; no publication, cloud, or website action occurs.

## Constraints

Stdlib runtime and existing `Principal`/`AgentRegistry` surfaces; additive
API; exact case-sensitive identifiers; bounded lists; fail closed; no new
dependency; no secrets in errors; no external publication.

## Assumptions

- The bearer token remains host-configured and maps to one local principal.
- An empty target allowlist means unrestricted within the principal's existing
  route scopes, preserving compatibility.

**Human confirmed:** no - additive bounded defaults recorded for review
