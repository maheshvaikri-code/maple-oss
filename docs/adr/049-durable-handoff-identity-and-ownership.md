# ADR-049: Local durable handoff identity and ownership

**Date:** 2026-08-26  
**Status:** accepted  
**Deciders:** Chief Architect, Backend, Security

## Context

`create_handoff_tool` already provided bounded, approval-aware local
delegation, but the delegation itself had no durable identity or explicit
ownership state. A process restart could therefore leave a host unable to
distinguish an accepted handoff from a completed one. The parity comparison
also makes ownership transfer distinct from manager-style agent-as-a-tool
return.

## Decision

Add a provider-neutral `HandoffStore` with thread-safe in-memory and atomic
file-backed implementations. `HandoffRecord` stores a bounded handoff ID,
source/target agent IDs, SHA-256 digests of the task and optional context,
status, current owner, target goal ID, failure type, and finite timestamps. Raw
task and context contents are not written by the store.

The state machine is:

`pending` (source-owned) → `accepted` (target-owned) → `completed` or `failed`
(source-owned). Only the target can finalize an accepted handoff; invalid
states and wrong owners fail closed. File records use the existing per-record
fencing lease and atomic replacement boundary.

When a store is supplied to `create_handoff_tool`, the tool creates and
accepts the record before invoking the target, then finalizes it after target
execution. The result exposes the handoff ID on success and on normalized
target failure. Store failures prevent target execution before acceptance and
surface a generic persistence error; a failed finalization surfaces the
uncertain ownership boundary rather than claiming success. Async store work is
run off the event loop.

## Alternatives considered

| Option | Pros | Cons | Why not |
|---|---|---|---|
| Optional local durable store with explicit transitions (chosen) | Small additive contract; restart visibility; no raw task persistence | Does not deliver or schedule work remotely | Fits the existing local runtime and fail-closed posture |
| Put handoff state in the agent run checkpoint | One persistence mechanism | Couples parent run state to target ownership and loses independent handoff identity | Handoffs can outlive a single local run boundary |
| Treat a target call as implicit ownership | Minimal code | Crashes and duplicate/retry decisions are ambiguous | Explicit state is required before claiming durable handoffs |
| Add distributed transport and exactly-once effects | Broader deployment parity | Requires auth, routing, idempotency, and side-effect contracts | Separate hosted/distributed project |

## Consequences

- Local hosts can inspect open or terminal handoff records after a process
  restart and correlate results by `handoff_id`.
- Ownership transfer is explicit and independently guarded by file leases.
- The store is an identity/state journal, not a queue, scheduler, remote
  transport, notification system, or exactly-once side-effect mechanism.
