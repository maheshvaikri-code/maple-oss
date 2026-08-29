# ADR-134: Owner-safe remote task retry

**Status:** Proposed
**Date:** 2026-08-29
**Decision owners:** Chief Architect / Backend / Security / QA

## Context

The task queue already supports bounded manual `requeue_task()` admission
after failure, but the authenticated remote control plane currently stops at
failure. A remote worker or operator must be able to request a retry without
opening an unrestricted queue handle. The existing local requeue method also
does not carry an owner, so the remote path needs an atomic ownership boundary.

## Decision

Add `POST /v1/tasks/{task_id}/retry` and
`RunClient.retry_task(task_id, assigned_agent)` under a new `task:retry`
scope. The request body contains only the assigned agent. The queue performs
the owner and state checks under its mutation lock: only a failed task with a
matching recorded owner may use the owner-aware path, and the existing retry
count/capacity bounds remain authoritative. A successful response returns the
requeued task envelope with a cleared owner and incremented retry count.

The optional owner argument on the local queue method preserves existing
no-owner compatibility for local scheduler callers. `FileTaskQueue` persists
the same transition through its durable fencing wrapper.

## Explicit boundary

This is explicit caller-driven retry, not automatic retry. It does not run a
handler, schedule a worker, reset a lease, retry a non-failed task, federate a
queue, or promise exactly-once external effects. Capacity rejection leaves the
failed task unchanged under the existing queue contract.

## Verification

Tests cover authenticated scope and principal policy, owner matching, failed
state requirements, retry count/capacity behavior, durable restart parity,
malformed input, and preservation of existing local requeue behavior.
