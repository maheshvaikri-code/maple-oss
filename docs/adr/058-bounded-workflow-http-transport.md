# ADR-058: Bounded Workflow HTTP Transport

- Status: Accepted
- Date: 2026-08-26
- Decision owners: Chief Architect, Backend, Security, QA

## Context

MAPLE already exposes a bounded loopback HTTP contract for starting,
resuming, and inspecting workflow runs. Agent frameworks commonly pair local
runtime APIs with a transport client, but the existing `RunServer` was not
usable by a caller that needed a consistent, bounded remote request surface.
The transport must not turn the loopback server into an unaudited public
service or imply that a network retry makes external effects exactly once.

## Decision

Add a dependency-free `RunClient` using the Python standard library and add an
optional bearer-token boundary to `RunServer`.

- `RunClient` accepts only `http` or `https` base URLs without user
  information, query strings, or fragments. It URL-encodes path segments and
  bounds request-body, path, and response bytes.
- The client returns MAPLE `Result` values. HTTP errors preserve the remote
  structured error when present; unreachable services, malformed JSON, and
  oversized responses have typed transport errors.
- The client performs no automatic retries. The caller owns retry, request
  identity, and idempotency policy for remote side effects.
- `RunServer(auth_token=...)` requires the exact `Authorization: Bearer ...`
  value for every route, including health. Comparison is constant-time and an
  unauthorized request receives `401` with `WWW-Authenticate: Bearer`.
- `RunServer` remains loopback-only. A production deployment may place a
  separately reviewed TLS/authentication proxy or hosted implementation in
  front of the contract; this slice does not implement TLS, tenancy, remote
  workflow registration, streaming, or sandboxing.

## Rejected alternatives

- Adding `requests` or another HTTP dependency would expand the release
  dependency surface for a small client contract.
- Binding `RunServer` to arbitrary interfaces would create a network exposure
  without TLS, tenant isolation, or a deployment policy.
- Retrying POST requests in the client would make duplicate workflow runs or
  external node effects ambiguous.

## Consequences

Local and hosted callers can share one bounded JSON workflow transport shape,
and local hosts can opt into a simple bearer authentication gate. The
contract remains deliberately lower-level than a managed runtime: TLS
termination, token issuance/rotation, authorization scopes, tenant isolation,
remote scheduling, and exactly-once effects remain host-owned follow-on work.
