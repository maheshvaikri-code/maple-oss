# ADR-060: Bounded Authenticated Human-Input Transport

- Status: Accepted
- Date: 2026-08-26
- Decision owners: Chief Architect, Backend, Security, QA

## Context

MAPLE already persists schema-validated human-input requests in bounded
in-memory or atomic file stores. The store boundary supports fail-closed actor
authorization, bounded multi-round history, and one-time consumption, but
operators cannot reach those records through the existing workflow HTTP
transport. An unauthenticated operator route would expose prompts, schemas, and
decisions; a hosted control plane would require tenancy, TLS termination,
deployment, and identity contracts that are not defined here.

## Decision

Extend the dependency-free loopback `RunServer`/`RunClient` contract with an
optional human-input store and bounded authenticated routes:

- `GET /v1/interactions/pending/<limit>` lists pending requests.
- `GET /v1/interactions/<interaction_id>` inspects one request.
- `POST /v1/interactions/<interaction_id>/respond` submits a response.
- `POST /v1/interactions/<interaction_id>/reject` records a rejection.
- `POST /v1/interactions/<interaction_id>/continue` opens the next bounded
  round.
- `POST /v1/interactions/<interaction_id>/consume` performs one-time consume.

The existing server bearer token protects every route before dispatch. Mutation
requests may include an `actor_id`; the configured store remains authoritative
for actor authorization, schema validation, persistence, notification, and
lease ownership. Request and response JSON bytes use the existing server
bounds, path segments are URL-encoded by `RunClient`, and store failures map
to structured HTTP errors. A missing store fails closed with `503`.

The server remains loopback-only and does not provide TLS, token issuance,
identity federation, tenancy, operator UI, remote scheduling, or automatic
run resume after a decision. A hosted deployment must supply those controls
and must not infer exactly-once external effects from this transport.

## Rejected alternatives

- Unauthenticated interaction routes would disclose human-input data and allow
  unauthorized mutations.
- Direct HTTP access to store files would bypass schema, leases, actor policy,
  notification, and typed error boundaries.
- A separate interaction daemon would duplicate the already bounded server
  authentication, body, response, and lifecycle machinery without closing a
  new local contract.
- Automatic run resumption after a remote response would couple transport
  delivery to agent scheduling and side-effect policy; resume remains an
  explicit host operation.

## Consequences

Hosts can connect an operator or control-plane adapter to the existing durable
interaction store without adding an HTTP dependency. The local transport now
covers listing, inspection, decision, bounded continuation, and consumption,
while the store still owns correctness and authorization. Remote deployment,
TLS, identity, audit retention, notification delivery, rate limiting, and
exactly-once side-effect policy remain separately reviewable boundaries.
