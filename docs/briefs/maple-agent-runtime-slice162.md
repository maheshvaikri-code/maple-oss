# Project Brief - MAPLE Agent Runtime Slice 162

**Class:** M
**Date:** 2026-08-28
**Owner:** Product Owner
**Problem:** The existing parent-agent execution journal can replay successful
tool results after a durable checkpoint failure, but the public
`create_agent_tool` factory always returns a non-replayable tool. A manager
that delegates to a local specialist therefore has no explicit way to reuse a
bounded successful child result during local recovery, even when the parent
has configured the journal.

## Scope

1. Add an opt-in `replay_policy` parameter to `create_agent_tool`.
2. Forward that policy to the returned `Tool`, preserving the current disabled
   default and existing approval/cancellation behavior.
3. Cover synchronous and asynchronous parent-tool replay with an in-memory
   execution journal and distinct tool-call IDs at the same run cursor.
4. Document the required parent journal and non-approval boundary, plus the
   existing at-least-once side-effect limitation.

## Acceptance criteria

1. `create_agent_tool(..., replay_policy=TOOL_REPLAY_REUSE_SUCCESS)` reuses a
   bounded successful result on a matching parent run/cursor without invoking
   the child a second time.
2. Sync and async parent execution preserve the returned tool-call ID while
   replaying only the serialized successful result.
3. The default remains `TOOL_REPLAY_DISABLED`; invalid policy values fail at
   tool construction through the existing validation.
4. Replay remains disabled for approval-required delegation because the
   existing approval outcome path owns that boundary.
5. Documentation states that this is local successful-result replay only;
   child-run restore, failed/cancelled replay, remote coordination, rollback,
   and exactly-once external effects remain outside the contract.

## Non-goals

- Reconstructing or resuming a child `AutonomousAgent` run.
- Replaying failed, cancelled, or malformed child results.
- Changing the execution-journal wire format or adding a dependency.
- Remote routing, distributed leases, scheduling, rollback, or exactly-once
  effects.

## Assumptions

- The parent agent supplies an `ExecutionJournal` and a durable `run_id`,
  `step_num`, and `tool_call_index` for replay to activate.
- The caller opts out of approval for this specific trusted local tool; the
  current parent replay guard intentionally excludes approval-required tools.
- Existing result bounds and journal conflict handling remain authoritative.

## Deferred

- Durable delegated child-run identity, restore/resume, and handoff result
  recovery require a separate lifecycle contract.
