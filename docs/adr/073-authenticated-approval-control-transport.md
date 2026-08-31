# ADR-073: Authenticated approval control transport

- **Status:** Accepted
- **Date:** 2026-08-27
- **Decision owners:** Chief Architect / Backend / Security

## Context

MAPLE already provides bounded in-memory and file-backed approval records,
durable decisions, and authenticated loopback transport for human-input
records. Approval-gated agent runs still require an operator to call the local
Python API directly. A host-owned control plane needs a small transport seam
for an approval UI or operator service without moving tool execution or
external-effect policy into the HTTP layer.

## Decision

Add optional authenticated `RunServer`/`RunClient` approval control routes:

- `GET /v1/approvals/pending/<limit>` lists bounded pending records;
- `GET /v1/approvals/<approval_id>` inspects one record;
- `POST /v1/approvals/<approval_id>/decide` records a boolean decision and an
  optional bounded edited-arguments object.

The configured `ApprovalStore` remains authoritative for validation, leases,
atomicity, conflict handling, and durable state. Configuring the transport
requires a bearer token. The route returns the store's bounded JSON-safe
record, and it does not consume approvals, execute tools, retry requests,
schedule work, issue tokens, or claim tenant isolation or exactly-once effects.

## Security and failure contract

The existing server body/path/response limits and bearer authentication apply.
Missing stores return a typed unavailable error; malformed limits, IDs, and
decision bodies fail before store mutation. Store errors retain their typed
HTTP mapping. Remote inspection may expose tool arguments and recorded result
content to an authenticated caller, so hosts own token scope, TLS, retention,
and sensitive-data policy; the loopback default remains the safe default.

## Alternatives considered

1. **Keep approvals local-only:** rejected because operators cannot integrate a
   bounded approval UI or service without embedding MAPLE in that process.
2. **Expose approval consumption/execution remotely:** rejected because a
   transport caller must not claim an approval without coupling it to the
   local agent handler and side-effect policy.
3. **Add a hosted identity/notification service:** deferred; it requires an
   explicit cloud, tenancy, token issuance, and delivery contract.

## Consequences

Remote operators can inspect and decide pending approvals through the same
authenticated dependency-free transport used by other local control surfaces.
The decision is still one bounded store mutation, and the local agent remains
responsible for consuming and executing it. Remote routing, notifications,
scheduling, token issuance, tenancy, and exactly-once effects remain separate.
