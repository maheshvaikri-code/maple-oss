# ADR-135: Authenticated remote task queue statistics

**Status:** Proposed
**Date:** 2026-08-29
**Decision owners:** Chief Architect / Backend / Security / QA

## Context

The authenticated task control plane now supports bounded lifecycle actions,
but operators and workers must still inspect individual tasks to understand
queue pressure. `TaskQueue` and `FileTaskQueue` already expose aggregate
`QueueStats` locally. A read-only remote view is useful for operational
visibility without adding a hosted metrics service.

## Decision

Add `GET /v1/tasks/stats` and `RunClient.task_queue_stats()` under the existing
`task:read` scope. The response contains only the fixed `QueueStats` counters
and finite timing/throughput values. The server validates the queue-owned
statistics envelope and returns a generic unavailable error if an optional
queue implementation returns malformed data.

The route is checked before the task-ID inspection route so `stats` is a
reserved aggregate endpoint. It performs no queue mutation and does not start,
stop, or poll the queue.

## Explicit boundary

This is bounded host-local queue telemetry, not a distributed metrics system.
It does not aggregate across queues or hosts, expose task payloads/results,
provide alerts or dashboards, or claim a consistent snapshot across separate
operations. Queue lifecycle, scheduling, and worker ownership remain outside
the route.

## Verification

Tests cover authenticated read scope, fixed response fields, finite-value
validation, malformed queue statistics, compatibility with in-memory and
durable queues, and route isolation from task-ID inspection.
