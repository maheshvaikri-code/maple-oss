# ADR-065: Bounded Authenticated Handoff Transport

- Status: Accepted
- Date: 2026-08-27
- Decision owners: Chief Architect, Backend, Security, QA

## Context

MAPLE's local `HandoffStore` already provides a bounded ownership state
machine and atomic file-backed fencing. Slice 118 added one-way authenticated
agent invocation, but it did not expose the handoff identity that coordinates
source and target ownership across processes. A transport can expose the
existing record contract without pretending to deliver the task payload or
provide hosted identity.

## Decision

Add an optional `HandoffStore` to `RunServer` and matching `RunClient`
operations:

- `POST /v1/handoffs` accepts a serialized `HandoffRecord` and returns the
  store's record result.
- `GET /v1/handoffs/<handoff_id>` inspects a record, and
  `GET /v1/handoffs/open/<limit>` lists bounded pending/accepted records.
- `POST /v1/handoffs/<handoff_id>/accept` accepts `target_agent_id`;
  `/complete` accepts `target_agent_id` and `target_goal_id`; `/fail` accepts
  `target_agent_id` and `error_type`.
- All routes use the existing loopback server, constant-time bearer
  authentication, bounded JSON/path/response limits, and `Result`-shaped
  errors. Attaching a handoff store requires `RunServer(auth_token=...)`.
- The record remains digest-only: task and context contents do not cross this
  transport. The source and target hosts coordinate those payloads through a
  separately authenticated channel or local store.
- The store remains authoritative for validation, conflicts, ownership, file
  fencing, and terminal transitions. The transport adds no retry, queue,
  scheduler, lease, principal scope, or delivery guarantee.

## Bounds and failure semantics

`HandoffRecord.from_dict` enforces bounded identifiers, SHA-256 digests,
allowed statuses, finite timestamps, and state invariants. The list route is
limited to 100 records; existing server request/path/response byte bounds
remain the outer transport limits. Missing records return `404`; invalid input
returns `400`; ownership/state conflicts return `409`; unavailable stores
return `503`.

The bearer token authenticates access to the configured transport but does not
identify a source or target principal. Hosts must place a scope-aware proxy or
identity layer in front of a non-loopback deployment before treating agent IDs
as authorization subjects.

## Alternatives considered

| Option | Pros | Cons | Decision |
|---|---|---|---|
| Expose the existing digest-only `HandoffStore` through the bounded HTTP contract | Reuses the tested state machine and file fencing without duplicating ownership logic | Requires the host to coordinate raw payloads separately; bearer auth is not per-agent identity | Chosen |
| Send task/context contents with every handoff transition | Easier for a standalone target | Expands sensitive-data exposure, replay/idempotency surface, and transport bounds | Rejected |
| Build remote handoff on a broker adapter | Could add asynchronous delivery | Couples the public contract to optional brokers and unclear delivery semantics | Deferred |

## Consequences

Source and target processes can inspect and transition one durable handoff
identity through a common authenticated contract while the existing stores
retain ownership correctness. The boundary still does not implement payload
delivery, principal authorization/scopes, notifications, retries,
cancellation, scheduling, durable remote results, or exactly-once external
effects.

## Reopening triggers

Reopen this ADR before adding raw payload delivery, agent-principal scopes,
automatic retries, queueing, notifications, cancellation, or a claim that a
remote handoff is delivered exactly once.
