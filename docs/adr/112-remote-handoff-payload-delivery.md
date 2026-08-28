# ADR-112: Adapt authenticated agent transport into remote handoffs

**Date:** 2026-08-28 · **Status:** accepted
**Deciders:** Chief Architect, Product Owner, Backend Engineer, Interop
Engineer, Security Reviewer

## Context

MAPLE already has two bounded contracts: `create_handoff_tool` owns local
handoff identity and ownership, while `RunClient.run_agent` sends a task and
bounded context to an authenticated host-owned `AgentRegistry`. The contracts
currently stop short of each other, so remote callers must manually coordinate
payload delivery and local finalization. `HandoffRecord` intentionally stores
digests rather than task or context contents, and the transport has no retry or
exactly-once guarantee.

The design must join these contracts without persisting raw handoff payloads,
weakening the existing context allowlist, or turning a synchronous HTTP call
into a scheduler or distributed transaction.

## Decision

We will add a public `RemoteHandoffTarget` adapter around `RunClient`. It will
implement the existing handoff target shape, forward only the already-bounded
task/context through `RunClient.run_agent`, use the active local `handoff_id`
as the remote `run_id` when available, accept only a validated completed remote
run, and return a bounded target result for the existing local handoff
finalizer. Sync and async methods share the same validation and generic failure
normalization; cancellation is checked before and after the request but is not
claimed to interrupt an in-flight HTTP call. The adapter performs no retry,
remote store mutation, queueing, scheduling, push notification, or exactly-once
side-effect coordination.

## Alternatives considered

| Option | Pros | Cons | Why not |
|---|---|---|---|
| **Adapter over existing `RunClient.run_agent` (chosen)** | Small additive surface; reuses authentication, bounds, server validation, and existing agent route; local handoff store remains authoritative | Synchronous remote execution; transport duplicate window remains | Fits the current contracts and closes payload delivery without adding a second protocol |
| Add raw task/context fields to `HandoffRecord` | One record appears self-contained | Persists sensitive payloads; changes durable schema and retention risk; broadens remote inspection exposure | Violates the digest-only handoff boundary |
| Add a new `/v1/handoffs/<id>/dispatch` server route | Could combine remote state and execution in one host | Requires remote record ownership semantics, per-agent identity, and a new transaction boundary | Prematurely couples transport, store, and execution; schedule as a separate design |
| Do nothing / document manual composition | Zero code churn | Leaves the primary remote handoff usability gap and duplicates failure logic in callers | Does not meet the parity objective |

## Consequences

- Positive: remote handoffs become a reusable tool target; task/context remain
  bounded and allowlisted; local ownership and result replay semantics remain
  unchanged; legacy local targets stay compatible.
- Negative / debt accepted: an HTTP timeout or crash after remote execution can
  leave the local handoff failed or uncertain and may permit a later caller to
  repeat an external effect; remote async resume, retry, and distributed
  deduplication are not solved.
- Invalidation triggers: a requirement for remote asynchronous handoff
  lifecycle, multi-principal identity federation, hosted routing/scheduling,
  or exactly-once side effects reopens this ADR and requires a new protocol and
  security design.
