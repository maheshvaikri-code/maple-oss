# ADR-147: distinguish omitted and explicitly invalid native run IDs

**Date:** 2026-08-29 · **Status:** accepted bounded correction
**Deciders:** Chief Architect; Backend Engineer

## Context

`Workflow.run` and the durable `AutonomousAgent` start boundary generated a
run ID with a truthiness fallback. Explicit `""` consequently bypassed the
existing identifier validation. The HTTP agent transport already validates its
raw request before applying its own generation path and is outside this ADR.

## Decision

Use `None` as the only omission sentinel. Generate an ID only when `run_id is
None`; pass every supplied value through the existing native validator/store
boundary. Preserve the agent's existing `RUN_STORE_ERROR` envelope for store
validation failures, with `RUN_IDENTIFIER_INVALID` retained as the bounded
cause. Reject before provider, session, checkpoint creation, or tool work.

## Consequences

- Callers can distinguish omitted IDs from explicitly invalid IDs.
- Existing generated-ID, duplicate-ID, resume, and transport behavior remains
  unchanged.
- The agent boundary continues to avoid leaking raw store errors.
- This does not provide distributed uniqueness, idempotency, scheduling, or
  exactly-once side effects.

## Verification

Sync and async agent regressions plus a workflow regression cover explicit empty
IDs. Full-suite, static, security, and package evidence is filed in the Slice
203 review and QA artifacts after the implementation commit.
