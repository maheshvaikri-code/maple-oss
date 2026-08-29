# ADR-146: authenticated local session control plane

**Date:** 2026-08-29 · **Status:** proposed pending human approval
**Deciders:** Chief Architect; human approval required by Doctrine §5

## Context

Slice 201 added bounded version history and data-only forks to the built-in
session stores, but the authenticated loopback control plane has no session
resource. The surrounding run, event, approval, handoff, and task surfaces
already use `RunServer`/`RunClient` and the host-owned `Principal` scope model.
The new surface would cross an authorization boundary and may return
conversation content, so it needs an explicit contract before implementation.

## Decision

We propose an optional `RunServer(session_store=...)` binding with three
additive routes: `GET /v1/sessions/{id}` and bounded
`GET /v1/sessions/{id}/history` under `session:read`, plus
`POST /v1/sessions/{id}/fork` under `session:fork`. The server will validate
IDs, query/body shape, versions, returned snapshot identity, JSON safety, and
response bounds before writing a response; it will call only the configured
host-owned store and will never execute or replay stored content. `RunClient`
will expose matching no-retry methods. Missing optional store capabilities
return 501, callback failures return generic 503, and remote forks require an
explicit target ID. This remains loopback/local-host functionality with no
tenancy, per-session ACL, encryption, distributed coordination, or
exactly-once claim.

## Data flow and failure paths

```text
HTTP request
  -> bearer authentication
  -> required session scope
  -> bounded path/query/body parse
  -> host-owned SessionStore load/history/fork
       -> typed store error -> stable HTTP error (no response content leak)
       -> typed snapshot(s) -> identity/JSON/size validation
  -> bounded JSON response

fork failure at any validation/store step -> no remote follow-up mutation
```

## Alternatives considered

| Option | Pros | Cons | Why not |
|---|---|---|---|
| Optional session resource on the existing authenticated control plane (proposed) | Reuses transport, auth, bounds, error mapping, and host-owned store; additive and easy to remove | Adds public routes/scopes and exposes sensitive session data to authorized callers | Proposed because it closes the local transport gap with one existing boundary |
| Couple session inspection/forking to `/v1/agents/{agent}/runs` | Fewer top-level routes | Wrong ownership model; sessions are not durable agent runs and would inherit agent-target policy | Reject: conflates resources and makes non-agent sessions inaccessible |
| Keep sessions local-only | Zero transport/security surface | Operators need storage access or bespoke endpoints; parity remains incomplete | Reject for the stated local-control-plane gap |

## Consequences

- Positive: local hosts gain one consistent authenticated inspection/branching
  boundary; existing session-store validation and data-only semantics remain
  authoritative; no new storage or dependency is required.
- Negative / debt accepted: `session:read` is coarse, remote fork is not
  retry-idempotent, and returning full snapshots requires host data-classification
  discipline. Hosted tenancy, per-session ownership, and encrypted transport
  remain future contracts.
- Invalidation triggers: any requirement for tenant isolation, remote session
  mutation, automatic retries, cross-process/distributed session ownership,
  encrypted persistence, or a response that omits/filters sensitive content
  reopens this ADR before implementation.

**Approval state:** implementation is intentionally paused pending the human
decision on the new public API and session-content exposure.
