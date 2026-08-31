# ADR-036: Add cross-process durable fencing leases

**Date:** 2026-08-26
**Status:** accepted

## Context

MAPLE already exposes an in-memory `LeaseManager` for thread-safe, TTL-bounded
resource ownership. File-backed approval, human-input, and run stores are
atomic within one process, but a host coordinating multiple MAPLE processes
needs a durable ownership primitive with restart-safe fencing tokens.

Without that boundary, two processes can independently observe a pending
record and attempt host work, and a stale process can continue after a lease
expires unless the guarded side effect checks a token.

## Decision

Add `FileLeaseManager` in `maple.resources.lease` with the same acquire,
renew, release, validity, holder, and held vocabulary as `LeaseManager`.

- Lease state and the monotonically increasing fencing counter are persisted
  as bounded JSON under a caller-owned directory.
- An advisory OS file lock serializes each read/modify/write operation across
  processes; the state file is replaced atomically after flush and fsync.
- Expiry uses wall-clock time so persisted leases remain meaningful after a
  process restart. TTLs are positive and bounded to seven days, and resource
  and holder identifiers are bounded to 256 characters.
- An exact `(resource, holder, token)` match is required for renewal,
  validity, and release. Stale tokens fail closed and cannot release a newer
  holder's lease.
- Corrupt or unavailable state returns a typed storage error for mutating
  operations and false/empty results for inspection operations.

The class is a host-coordination primitive. It does not claim exactly-once
external side effects, does not automatically wrap approval or human-input
stores, and does not replace a distributed database or a service-specific
fencing check at the guarded resource.

## Alternatives considered

1. Keep the in-memory manager only. Rejected because process restarts and
   multiple workers require durable ownership.
2. Use a new dependency for file locking. Rejected for this local boundary;
   the standard-library OS locking APIs keep the package dependency-free.
3. Treat file replacement as sufficient concurrency control. Rejected because
   atomic replacement alone does not serialize competing read/modify/write
   decisions.
4. Integrate leases into every durable store immediately. Deferred until the
   approval/input/run ownership and side-effect policy are specified together.

## Consequences

Hosts can coordinate multiple local MAPLE processes with restart-safe fencing
tokens and explicit failure semantics. The lock file and JSON state are
caller-owned operational data and require filesystem access controls. A host
must present the current fencing token to the guarded resource immediately
before acting; the lease manager cannot stop an already-running external side
effect.

## Invalidation triggers

Revisit this ADR before claiming distributed or hosted runtime parity, adding
automatic durable-store ownership, promising exactly-once effects, or adding
authenticated remote lease service support.
