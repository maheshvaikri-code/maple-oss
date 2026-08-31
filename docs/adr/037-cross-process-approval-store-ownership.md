# ADR-037: Lease file-backed approval records across processes

**Date:** 2026-08-26
**Status:** accepted

## Context

`FileApprovalStore` persists approval decisions atomically, but atomic file
replacement alone does not serialize two processes making a decision or
consuming an approval. Approval is a side-effect gate: a process must not
execute a tool from a stale view of the pending record.

## Decision

`FileApprovalStore` will create a caller-owned `.maple-leases` directory by
default and acquire a short-lived `FileLeaseManager` fencing lease for every
record operation (`get`, `create`, `decide`, `consume`) and the bounded pending
list operation. The record identifier is namespaced as `approval:<id>`; the
store holder is unique per process/store instance; the default lease TTL is
30 seconds and may be overridden with a positive keyword-only option.

Lease acquisition happens before file reads or writes. A failed acquisition
returns `APPROVAL_LEASE_ERROR` and performs no record mutation. The existing
thread lock and atomic JSON replacement remain in place. A failed release
returns `APPROVAL_LEASE_RELEASE_ERROR`; callers must treat a successful
mutation with that result as an uncertain commit and inspect the durable
record before retrying.

## Alternatives considered

| Option | Pros | Cons | Why not |
|---|---|---|---|
| Per-record file lease (chosen) | Reuses MAPLE fencing primitive; small blast radius; restart-safe | Local filesystem scope; release uncertainty needs caller handling | Best fit for the existing file store and zero runtime dependencies |
| One global store lease | Simple implementation | Serializes unrelated approvals and increases contention | Too coarse for a multi-record approval store |
| Atomic replacement only | No additional state | Does not serialize read/modify/write decisions | Insufficient for a side-effect gate |
| Remote database/lock service | Stronger hosted coordination | New dependency, deployment, auth, and paid-service boundary | Requires a separately approved hosted contract |

## Consequences

Separate MAPLE processes sharing the same approval directory now fail closed
when another holder owns the record lease. The lease directory is operational
state owned by the host and must use appropriate filesystem permissions. The
store still does not send notifications, authenticate a remote human, or make
external tool effects exactly once; handlers remain responsible for
idempotency and fencing checks at the side-effect boundary.

## Invalidation triggers

Revisit this ADR before integrating a remote approval service, changing the
decision API to multi-round interaction, promising exactly-once external
effects, or applying the same ownership helper to input/run stores without
their own recovery and side-effect analysis.
