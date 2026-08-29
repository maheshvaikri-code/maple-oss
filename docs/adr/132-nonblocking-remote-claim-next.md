# ADR-132: Non-blocking remote claim-next

**Status:** Proposed
**Date:** 2026-08-28
**Decision owners:** Chief Architect / Backend / Security / QA

## Context

Slice 186 exposed authenticated task submission, inspection, and claim-by-ID.
Workers still had to list tasks and perform their own compatibility filtering
before claiming. That is functional but awkward and creates avoidable races
between candidate selection and the queue's atomic ownership transition.

## Decision

Add `POST /v1/tasks/claim-next` and `RunClient.claim_next_task(...)` under the
existing `task:claim` scope. The request contains an assigned agent and an
optional bounded capability list. The server reads at most the remote task
list bound, orders candidates by priority, creation time, and task ID, skips
tasks whose requirements are not satisfied, and uses the existing atomic
`TaskQueue.assign_task()` transition. If another worker wins a candidate, the
server tries the next candidate; if none is compatible it returns
`{"task": null}`.

The operation is deliberately non-blocking. It does not call the queue's
consumer wait loop or start/stop the queue; hosts retain ownership of queue
lifecycle and worker polling cadence. It applies principal agent and
capability allowlists before reading or mutating queue state.

## Explicit boundary

This is bounded worker ergonomics, not a distributed scheduler. It does not
add worker heartbeats, leases, automatic retry, queue federation, fairness
across hosts, atomic submit-and-claim, handler execution, or exactly-once
external effects. Queue ordering and ownership remain the selected queue
implementation's authority; the route only provides a bounded candidate
selection policy.

## Verification

Tests cover capability filtering, priority ordering, no-compatible-task
responses, principal policy, and compatibility with the Slice 186 task
control routes. Package and clean archive evidence is recorded after the
implementation and release-doc commit.
