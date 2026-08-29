# ADR-131: Authenticated remote task-queue control plane

**Status:** Proposed
**Date:** 2026-08-28
**Decision owners:** Chief Architect / Backend / Security / QA

## Context

MAPLE now has a bounded in-process `TaskQueue` and a file-backed
`FileTaskQueue` that survives local restarts. A separate process can persist
and inspect work only through host-specific code, however, so the runtime
still lacks a small authenticated control surface for task admission and
worker ownership transitions.

## Decision

Add an optional `task_queue` to the loopback `RunServer` and expose the same
queue through additive `RunClient` methods:

- `POST /v1/tasks` and `RunClient.submit_task(...)` admit one bounded task;
- `GET /v1/tasks` and `RunClient.list_tasks(...)` inspect bounded records;
- `GET /v1/tasks/{task_id}` and `RunClient.inspect_task(...)` inspect one record;
- `POST /v1/tasks/{task_id}/claim` atomically assigns one worker;
- `POST /v1/tasks/{task_id}/complete` records an owner-checked result; and
- `POST /v1/tasks/{task_id}/fail` records an owner-checked failure.

The routes require the distinct `task:submit`, `task:read`, `task:claim`,
`task:complete`, and `task:fail` scopes. When a principal has exact agent or
capability allowlists, submit requirements and worker ownership are checked
before queue mutation. A configured queue requires authentication. Queue
state and lifecycle semantics remain authoritative in the selected
`TaskQueue` implementation.

The HTTP boundary accepts only bounded JSON-safe payloads and metadata,
bounded capability requirements, known priority values, finite timeout/retry
integers, and bounded task results/failure text. Queue-owned error strings are
mapped to stable typed HTTP errors without returning filesystem or internal
details. The client performs the same validation before making a request.

## Explicit boundary

This is a control plane, not a distributed scheduler. It does not add worker
heartbeats, leases, polling, automatic retry, queue federation, atomic
submit-and-claim, idempotency keys, handler invocation, or exactly-once
external effects. `FileTaskQueue` continues to provide only local
cross-process fencing and explicit at-least-once restart recovery. Hosts own
worker lifecycle, TLS, token issuance, tenancy, and execution policy.

## Alternatives considered

1. **Expose the queue without authentication.** Rejected because task payloads,
   results, and ownership are control-plane data and the existing server
   requires authentication for optional stateful services.
2. **Add a distributed broker or scheduler.** Rejected because it would
   introduce a provider/dependency and worker-liveness contract beyond this
   repository's current local boundary.
3. **Reuse agent invocation routes.** Rejected because task admission and
   agent execution have different ownership, retry, and side-effect semantics.

## Verification

Tests cover authenticated round trips, queue configuration requirements,
scope and principal policy, owner conflicts, malformed task/query/result
inputs, and no-credential rejection. Package, static, security, and clean
archive evidence is recorded after the implementation is complete.
