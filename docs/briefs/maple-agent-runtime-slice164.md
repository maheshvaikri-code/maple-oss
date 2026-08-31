# Project Brief - MAPLE Agent Runtime Slice 164

**Class:** L
**Date:** 2026-08-28
**Owner:** Product Owner
**Problem:** `create_agent_tool` delegates to a child agent, but a caller cannot
resume an in-flight durable child after a crash or retry. Parent tool-result
replay covers only a completed result already recorded in the parent journal;
it does not restore the child's own run cursor.

## Scope

1. Add an opt-in `persist_child_run=True` mode to `create_agent_tool`.
2. Require a caller-supplied bounded `child_run_id` in that mode and pass it to
   the native sync/async child goal APIs.
3. When a child run already exists, resume it through the child's native
   `resume_run` or `resume_run_async` API instead of starting a second run.
4. Preserve bounded context filtering, cancellation propagation, result
   redaction, approval defaults, and existing legacy targets.
5. Keep the lifecycle local and host-owned; no remote routing or scheduler is
   introduced.

## Acceptance criteria

1. The default factory signature and schema remain unchanged when
   `persist_child_run` is disabled.
2. Enabling persistence validates the target's run and resume contracts and
   exposes a required `child_run_id` input with the native run-ID bounds.
3. Sync and async retries with the same ID receive a native resume call after
   an existing-run response; the child is not started as a second run.
4. Context-aware children receive the same bounded context on first start;
   resume uses the durable child checkpoint and does not re-send context.
5. Invalid IDs, missing target capabilities, completed/failed/cancelled child
   runs, cancellation, and malformed child results fail closed with bounded
   errors; no raw child payload or exception is exposed.
6. Existing non-persistent agent tools and handoffs remain behaviorally
   compatible, and all tracked tests/static/package gates remain green.

## Threat sketch

- **Assets:** child-run identity, checkpoint state, delegated output, and
  parent/child ownership boundaries.
- **Entry points:** factory configuration, model-supplied `child_run_id`, child
  resume callbacks, and persisted native run checkpoints.
- **Worst plausible abuse:** reusing an ID for another task, causing a second
  side effect, or exposing child checkpoint data. The native run store owns
  identity conflicts, the factory requires explicit IDs, and the result
  formatter continues to return only bounded agent/goal/status/result fields.

## Non-goals

- Remote child-run restore, routing, scheduling, queue ownership, or hosted
  workers.
- Automatic child-ID generation or deriving identity from task text.
- Replaying completed terminal child results outside the existing parent
  execution journal.
- Hard cancellation, rollback, exactly-once effects, or cross-store
  transactions.

## Deferred

A first-class distributed child lifecycle requires a reviewed ownership,
resume-token, delivery, retention, and side-effect policy. This slice keeps
that boundary explicit.
