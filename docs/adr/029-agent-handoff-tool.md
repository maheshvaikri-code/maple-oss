# ADR-029: Bounded agent-as-tool handoffs

**Date:** 2026-08-25  
**Status:** accepted  
**Deciders:** Chief Architect

## Context

MAPLE already supports explicit teams and message-based delegation, but a
single autonomous agent could not expose a specialist as a normal model tool.
That is a common agent-framework composition primitive: the model can delegate
one bounded task and receive a structured result without the host writing a
custom adapter for every specialist.

## Decision

Add `create_handoff_tool(target_agent, ...)` to the dependency-free autonomy
tool layer. It creates a normal `Tool` whose bounded `task` string invokes the
target's synchronous `pursue_goal` method and returns the target goal ID,
status, result, and agent ID. Target failures are normalized to
`HANDOFF_TARGET_FAILED`, target exceptions to `HANDOFF_TARGET_ERROR`, and
invalid target return values to `HANDOFF_TARGET_INVALID`; raw failure payloads
are not copied into the caller's model context.

The task is constrained to 8,192 characters and rejects additional arguments.
Handoffs require approval by default because they can trigger tools and external
side effects in the target agent; trusted hosts may opt out explicitly. Async
MAPLE turns use the existing executor-backed tool-call path for this synchronous
handoff, so the event loop is not blocked. The target handler remains subject
to its own agent budgets and approval policies.

## Alternatives considered

| Option | Pros | Cons | Why not |
|---|---|---|---|
| Normal bounded `Tool` handoff (chosen) | Reuses schemas, approval, tracing, and sync/async tool paths | Target call is synchronous and cooperative | Smallest composable primitive with existing safety controls |
| Add a new orchestration-only handoff protocol | Richer routing and lifecycle metadata | Duplicates tool and approval contracts; larger public surface | Team orchestration already covers multi-agent plans |
| Pass the target agent directly into model/provider code | Fewer wrapper lines | Bypasses tool schema, approval, and structured errors | Violates the existing tool boundary |
| Add a distributed handoff broker | Cross-process scale and durability | New state/deployment/dependency contract | Deferred with distributed execution |

## Consequences

- Positive: agents can delegate bounded specialist tasks through the same model
  tool contract used for ordinary tools.
- Positive: approval, input validation, provider schema publication, and
  structured failure handling are reused instead of forked.
- Negative / debt accepted: this is local synchronous target invocation, not
  durable routing, hard cancellation, or a distributed handoff protocol.
- Invalidation triggers: provider-native handoff APIs, cross-process target
  execution, or a requirement to transfer full conversation state.
