# Project Brief - Native Agent-Run Cancellation

**Date:** 2026-08-28  · **Class:** L  · **Requested by:** human

## Problem

MAPLE already exposes a thread-safe `CancellationToken` for bounded trusted
execution and orchestration, but native synchronous and asynchronous ReAct
goals have no caller-owned cancellation input. A host therefore cannot stop
future model/tool turns through the agent API or persist a truthful terminal
state for a durable run.

## Scope

- **In:** Optional `CancellationToken` parameters on native sync/async goal
  entry points and resume paths; cooperative checks at model/tool/reflect/
  checkpoint boundaries; propagation into `Tool` and `ToolRegistry` execution;
  durable `cancelled` checkpoints and metadata-only lifecycle events; typed
  cancellation errors; regression and boundary tests; public documentation.
- **Non-goals:** Hard thread termination; provider-specific abort protocols;
  cancellation of arbitrary async handlers already in progress; distributed
  cancellation; remote transport changes; exactly-once external effects;
  website changes; publication or deployment.
- **Deferred:** Provider-native request aborts and a remote token propagation
  contract require separate provider and transport briefs.

## Acceptance criteria

1. Sync and async `pursue_goal` accept a caller-owned cancellation token and
   return a `Goal` with `status == "cancelled"` and typed
   `AGENT_RUN_CANCELLED` result when cancellation is observed.
2. Sync and async `resume_run` accept the same token; terminal checkpoints are
   not resumable, and cancellation before resolving a paused interaction does
   not consume or mutate that interaction.
3. A cancellation observed before a future model/tool/reflect turn prevents
   that turn; cancellation during an in-flight provider or ordinary handler
   is cooperative and prevents subsequent turns after the current call
   returns.
4. Executor-backed tools receive the token and retain the existing bounded
   `EXECUTION_CANCELLED` behavior; non-executor handlers are never passed an
   unexpected keyword argument.
5. Durable cancellation persists a JSON-safe `cancelled` checkpoint with no
   pending interaction ID, bounded error metadata, current cursor/usage, and
   emits a metadata-only `run.cancelled` event when an event stream is bound.
6. Invalid cancellation values fail closed with a deterministic typed error;
   omitted tokens preserve existing behavior.
7. Focused tests cover sync, async, durable, executor, invalid-input, and
   paused-interaction boundaries. Existing tracked tests remain green.

## Constraints

- Preserve `Result<T, E>` conventions and existing positional/keyword call
  compatibility.
- Use the existing standard-library `CancellationToken`; no dependency or
  provider SDK changes.
- Never claim force termination or exactly-once side effects. A cancellation
  boundary may follow an already-started external effect.

## Assumptions

- `CancellationToken` remains the host-owned signal and is safe to share
  across the calling thread and executor workers.
- A paused run remains paused if cancellation is requested before its pending
  approval/input is resolved; this preserves the request for an explicit host
  decision and avoids orphaning a side-effect gate.

## Open questions

- None block this local slice.

**Human confirmed:** yes - continuation of the direct build request on
2026-08-28.
