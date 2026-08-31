# ADR-117: Opt-in Remote Handoff Idempotency Binding

**Date:** 2026-08-28
**Status:** accepted
**Deciders:** Chief Architect, Backend Engineer, Interop, Security Reviewer

## Context

The remote handoff adapter accepts an explicit `handoff_id` and maps it to the
remote agent run ID. Slice 171 adds a host-owned idempotency boundary to
`RunClient.run_agent`, but leaving the adapter unaware of that field means a
caller retry can still run a remote handoff handler twice.

## Decision

Add `use_handoff_id_as_idempotency_key=False` to `RemoteHandoffTarget`. The
default remains byte-for-byte compatible with the existing call: the adapter
sends the handoff ID only as `run_id`. When the option is true, the adapter
requires a bounded explicit `handoff_id` and sends that same value as both
`run_id` and `idempotency_key` to `RunClient.run_agent(...)`. The receiver must
configure an `AgentInvocationDeduplicationStore`; otherwise its existing
fail-closed `AGENT_INVOCATION_STORE_UNAVAILABLE` response is normalized by the
adapter as a remote handoff failure.

The binding is applied by the shared synchronous `_invoke` path, so the async
executor-backed methods inherit identical behavior. The receiver computes the
request digest from the normalized agent target/task/context/session/run
fields. A matching completed response can replay, an in-flight duplicate is a
typed conflict, and different request content remains a receiver-side
conflict. The adapter performs no retry, waits for no pending claim, and does
not create a key when no handoff ID is supplied.

## Consequences

- Positive: a host can connect its durable local handoff identity to the
  bounded remote retry guard with one explicit configuration flag.
- Negative / debt accepted: the receiver must opt into a compatible store;
  TTL/eviction and crash windows remain, and external side effects are still
  at-least-once rather than exactly once.
- Existing callers retain the old behavior unless they opt in.

## Alternatives considered

| Option | Why not |
|---|---|
| Always use `handoff_id` as the remote key | Breaks receivers that do not configure the new store and changes existing wire behavior |
| Generate a UUID key when no handoff ID is supplied | A retry cannot reproduce the key; it creates false confidence and no durable identity |
| Add a separate handoff/idempotency mapping service | Requires distributed ownership, identity, persistence, and deployment contracts outside this local-first slice |

## Security and failure boundary

The option does not broaden authentication or authorization. The existing
bearer token and `agent:invoke` scope remain authoritative. IDs are bounded and
control-free before the request; remote errors are still reduced to the
adapter's sanitized failure envelope. No task/context payload or credential is
logged or persisted by the adapter.
