# Project Brief - MAPLE Agent Runtime Slice 163

**Class:** L
**Date:** 2026-08-28
**Owner:** Product Owner
**Problem:** A durable local handoff records ownership and terminal identity,
but not the bounded successful result. After a parent crash window, a caller
cannot reuse a completed handoff result and may invoke the specialist again.
This leaves handoff recovery behind the existing agent-as-tool replay surface.

## Scope

1. Add an optional bounded JSON result to completed `HandoffRecord` values while
   accepting older persisted records that do not contain that field.
2. Extend the built-in in-memory and file stores to persist the result only
   when the handoff factory explicitly enables it.
3. Add an explicit optional `handoff_id` input so a retry can address the same
   handoff identity; a completed record with a valid stored result returns it
   without invoking the target.
4. Preserve sync/async execution, cancellation, ownership fencing, and
   at-least-once behavior for new or incomplete handoffs.
5. Keep remote handoff transport digest-only; result payloads must never be
   emitted by `RunServer` or accepted through its completion route.

## Acceptance criteria

1. `create_handoff_tool(..., persist_result=True, handoff_store=...)` requires
   a store with the extended completion capability and fails closed otherwise.
2. Sync and async retries with the same explicit `handoff_id` replay only a
   bounded successful result and do not invoke the child again.
3. Failed, cancelled, malformed, or result-less completed records never replay
   as success; active/accepted records remain protected by store state checks.
4. File-store restart preserves a valid opted-in result; legacy records without
   `result` remain loadable and digest-only remote payloads omit it.
5. Existing callers without `persist_result` or `handoff_id` retain the current
   generated-ID behavior and all existing tests remain green.

## Threat sketch

- **Assets:** child result data, handoff ownership, and durable replay identity.
- **Entry points:** local factory options, explicit handoff IDs, file JSON, and
  authenticated remote handoff inspection/completion.
- **Worst plausible abuse:** a caller persists oversized or sensitive output,
  reuses an ID across different task/context inputs, or leaks stored output
  through the remote inspection API; all are bounded, identity-checked, or
  redacted by this design.

## Non-goals

- Hard termination, remote result delivery, child-run restore/resume, rollback,
  or exactly-once external effects.
- Persisting results by default or changing the remote handoff wire contract.
- Retrying accepted/in-flight work automatically after a process crash.

## Deferred

- A first-class delegated child-run lifecycle with remote ownership transfer,
  resume tokens, and operator reconciliation remains a separate capability.
