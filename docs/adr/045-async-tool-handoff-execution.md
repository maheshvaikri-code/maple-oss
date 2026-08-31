# ADR-045: Async tool and handoff execution

**Date:** 2026-08-26  
**Status:** accepted  
**Deciders:** Chief Architect

## Context

MAPLE already exposed an asynchronous agent entry point, but its tool-call
worker always invoked the synchronous `Tool.execute` path. That preserved
event-loop safety for legacy handlers, but it prevented an async-native tool or
specialist agent from using its declared awaitable contract. Async handoffs
also need the same bounded context and error boundary as synchronous handoffs.

## Decision

Add an optional `Tool.async_handler`, `Tool.execute_async`, and
`ToolRegistry.execute_async` contract. `Tool.execute_async` performs the same
input validation, input guardrails, output validation, and output guardrails
as the synchronous path. When an async handler is declared it is awaited
directly; otherwise the existing synchronous `execute` path runs in the
default executor so legacy tools remain usable without blocking the event
loop.

The asynchronous `AutonomousAgent` tool-call path resolves approval and
durable approval-store work in an executor, then awaits `Tool.execute_async`.
Human-input request persistence remains executor-backed. Approval remains an
agent boundary: direct calls to a `Tool` are host-owned just as they are for
the synchronous API.

`create_handoff_tool` uses a target's `pursue_goal_async` method when present.
Non-empty context requires an explicit
`pursue_goal_with_context_async(task, context)` method. Context filtering,
recursive JSON bounds, target-result normalization, and raw-error redaction
are shared with the synchronous handoff contract.

## Alternatives considered

| Option | Pros | Cons | Why not |
|---|---|---|---|
| Optional async handler with sync fallback (chosen) | Compatible migration path; one validation and approval boundary; native async targets | A tool still carries a sync handler for compatibility | Smallest safe extension to the existing public `Tool` contract |
| Require every tool to be async | Simple async loop | Breaks existing tools and forces unnecessary migration | Incompatible with MAPLE's current synchronous API |
| Keep all async turns on sync workers | No runtime refactor | Async-native providers and handoffs cannot be awaited | Leaves a material async parity gap |
| Add a separate async tool type | Explicit contracts | Duplicates schema, guardrail, approval, and registry behavior | Increases public surface without improving the safety boundary |

## Consequences

- Positive: async agent turns can await async-native tools and local handoff
  targets while retaining synchronous-tool compatibility.
- Positive: approval, bounded inputs, guardrails, and structured errors remain
  enforced at the same agent/tool boundary.
- Negative / debt accepted: cancellation of a synchronous fallback or an
  already-started async handler is cooperative; MAPLE does not claim hard
  interruption or exactly-once external side effects.
- Negative / debt accepted: this is still local handoff execution. Durable
  handoff identity, ownership transfer, remote routing, and transport auth
  remain separate capabilities.

