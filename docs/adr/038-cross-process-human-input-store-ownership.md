# ADR-038: Lease file-backed human-input records across processes

**Date:** 2026-08-26
**Status:** accepted

## Context

`FileHumanInputStore` persists bounded questions and host decisions, but a
response or rejection can arrive from a different process than the one that
created the request. Atomic JSON replacement protects bytes, not ownership of
the pending-to-decided transition.

## Decision

`FileHumanInputStore` will use the shared durable-record lease wrapper with a
`human-input:<interaction_id>` namespace. By default it creates or reuses the
caller-owned `<directory>/.maple-leases` directory; callers may inject a
`FileLeaseManager` and override the positive, bounded lease TTL with keyword
arguments.

The store acquires the lease before `get`, `create`, `respond`, `reject`,
`consume`, and bounded `list_pending` operations. Acquisition failure returns
`HUMAN_INPUT_LEASE_ERROR` without mutating the request. Release failure returns
`HUMAN_INPUT_LEASE_RELEASE_ERROR`; a successful mutation may already be
durable, so the host must inspect the record before retrying.

Schema validation and rejection-reason validation remain inside the leased
operation. Invalid responses therefore leave the pending record unchanged even
when another process is concurrently attempting a response.

## Alternatives considered

| Option | Pros | Cons | Why not |
|---|---|---|---|
| Per-record fencing lease (chosen) | Reuses one tested boundary; small contention scope; restart-safe | Local filesystem scope; uncertain release commit | Matches the existing file store and bounded local runtime |
| Approval-only lease ownership | Smaller immediate diff | Leaves host input races unresolved | Human input is itself a pending side-effect boundary |
| Global input-store lease | Easy to reason about | Serializes unrelated forms and list calls | Too coarse for concurrent requests |
| Remote notification/coordination service | Can authenticate and notify operators | New service, auth, dependency, and deployment contract | Deferred to an explicitly approved hosted boundary |

## Consequences

Multiple local MAPLE processes can safely compete to answer one persisted form;
only the current fencing holder may transition the record. The store still
does not notify a host, authenticate a human, support multi-round forms, or
promise exactly-once external effects. Host filesystem permissions and
idempotent downstream handlers remain required.

## Invalidation triggers

Revisit this ADR before adding remote operator authentication, notifications,
multi-round interaction state, or automatic lease ownership for run cursors
whose side-effect policy has not yet been specified.
