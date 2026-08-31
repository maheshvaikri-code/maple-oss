# ADR-039: Lease file-backed run checkpoints across processes

**Date:** 2026-08-26
**Status:** accepted

## Context

`FileAgentRunStore` atomically replaces checkpoint files and uses an in-process
lock, but a durable run can be loaded or compare-and-set by a different MAPLE
process after a restart. Atomic replacement protects bytes; it does not by
itself establish which local worker owns the run cursor while it is being
read, advanced, or resumed.

## Decision

`FileAgentRunStore` will use the shared durable-record lease wrapper with a
`run:<run_id>` namespace. By default it creates or reuses the caller-owned
`<directory>/.maple-leases` directory; callers may inject a `FileLeaseManager`
and override the positive lease TTL with keyword arguments.

The store acquires the lease before `load` and before the complete
compare-and-set `save` operation. Acquisition failure returns
`RUN_CHECKPOINT_LEASE_ERROR` without reading or mutating the checkpoint.
Release failure returns `RUN_CHECKPOINT_LEASE_RELEASE_ERROR`; a successful
save may already be durable, so the host must inspect the checkpoint before
retrying.

The existing in-process reentrant lock, bounded JSON validation, atomic
temporary-file replacement, and expected-version conflict remain unchanged.
The lease fences checkpoint ownership only; it does not make tool calls,
provider requests, notifications, or other external effects exactly once.

## Alternatives considered

| Option | Pros | Cons | Why not |
|---|---|---|---|
| Per-run fencing lease (chosen) | Reuses one tested boundary; preserves CAS semantics; limits contention to one run | Local filesystem scope; uncertain release commit | Matches the existing local durable-run contract |
| Global run-store lease | Simple ownership model | Serializes unrelated runs and reads | Too coarse for multi-run hosts |
| CAS-only file replacement | No additional coordination | Two workers can both act on the same loaded cursor | Does not establish active run ownership |
| Remote coordinator | Supports hosted workers and stronger identity | Adds service, auth, deployment, and dependency contracts | Deferred until a hosted runtime is explicitly scoped |

## Consequences

Multiple local MAPLE processes can safely contend for one persisted run cursor;
only the current fencing holder may load or advance it. Hosts still need an
idempotent side-effect policy around tools and providers, and must not infer
exactly-once execution from checkpoint durability alone. Notifications,
operator authentication, distributed worker identity, and cancellation remain
outside this slice.

## Invalidation triggers

Revisit this ADR before adding remote worker coordination, authenticated host
notifications, automatic side-effect replay, or a hosted execution service.
