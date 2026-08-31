# ADR-109: Opt-in local delegated child-run lifecycle

**Date:** 2026-08-28
**Status:** accepted
**Deciders:** Chief Architect

## Context

`create_agent_tool` currently performs a manager-style child invocation. The
parent can optionally replay a completed normalized result from its execution
journal, but an interrupted child with its own durable `AgentRunStore` has no
factory-level retry path. Starting the child again would conflict with its
run ID or, for an adapter that hides that conflict, could repeat work.

## Decision

Add an opt-in `persist_child_run` factory option. When enabled, callers must
provide a bounded `child_run_id` to each tool call. The factory passes that ID
to the child's `pursue_goal`/`pursue_goal_with_context` or async equivalents.
If the child reports that the run ID already exists, the factory calls the
child's matching native `resume_run` or `resume_run_async` method. The child
agent remains responsible for configuring its own `AgentRunStore`, checkpoint
validation, approval/input recovery, and terminal-state rules.

The default remains disabled. Persistent child mode validates the required
callable/signature surface at factory creation and validates the ID at the
tool boundary. Normal result formatting still strips raw child errors and
returns only the bounded normalized envelope. The retry's existence probe may
repeat the bounded start call, but the native resume call itself receives only
the child ID and uses the child checkpoint rather than starting another model
turn or forwarding context into the resumed loop.

## Data flow and failure modes

```text
task + bounded child_run_id + filtered context
  -> child pursue(..., run_id=child_run_id)
  -> success: normalize bounded child result
  -> RUN_EXISTS: child resume_run(child_run_id)
  -> RUN_NOT_FOUND / terminal / store / callback failure: bounded target error
```

- The child run ID is explicit and is part of the persisted parent tool-call
  arguments when a durable parent run is used.
- A `RUN_EXISTS` response is the only signal that changes start into resume;
  arbitrary child failures are never retried or hidden behind a resume attempt.
- The feature does not inspect or mutate a child store directly and therefore
  does not claim a cross-store transaction or exactly-once effects.
- A completed result is not independently replayed by this factory. Callers
  may use the existing parent `ExecutionJournal` contract when appropriate.

## Consequences

- Local manager-style delegation can continue an in-flight native child after
  a retry, including durable approval or human-input recovery owned by the
  child agent.
- The caller must allocate and retain a stable child ID, and the child must
  expose the native durable run APIs.
- Legacy child adapters keep their current behavior when the option is off.
- Remote delegation, distributed scheduling, hard termination, rollback, and
  exactly-once external effects remain outside MAPLE's claim.

## Alternatives considered

| Option | Pros | Cons | Why not |
|---|---|---|---|
| Explicit ID plus native child resume (chosen) | Small additive seam; reuses tested child checkpoints and approval/input recovery | Caller must provide an ID; terminal result replay stays separate | Delivers local in-flight recovery without inventing a second store |
| Generate child IDs inside the factory | Easier first call | Parent crash before tool output can lose the ID | Recovery identity must be caller-visible and durable |
| Copy child checkpoints into the parent store | One persistence boundary | Duplicates state, creates cross-store fencing and migration issues | Violates ownership separation |
| Retry the child with a new ID | Simple implementation | Repeats side effects and loses in-flight state | Unsafe for durable delegation |

**Invalidation triggers:** a reviewed remote child ownership protocol, a
cross-store transaction design, or a terminal child-result replay contract.
