# ADR-026: Bounded concurrent multi-agent orchestration

**Date:** 2026-08-25
**Status:** accepted
**Deciders:** Chief Architect

## Context

MAPLE's supervisor and consensus patterns already supported delegation, but
their independent worker calls were executed serially. That left a material
runtime gap against agent frameworks that fan out independent specialists while
preserving a deterministic join.

## Decision

`AgentOrchestrator` now accepts an additive `max_parallel_agents` limit from 1
through 64, defaulting to 8. Synchronous supervised and consensus execution
uses a bounded thread pool; asynchronous variants use a bounded semaphore and
prefer each member's `pursue_goal_async` method, falling back to an executor for
sync-only agents. Results are collected in assignment/member order regardless
of completion order.

Worker exceptions are normalized to `AGENT_EXECUTION_ERROR` for the affected
member while sibling work continues. The boundary assumes independent agent
goals; shared mutable application state remains the host's responsibility.

## Alternatives considered

| Option | Pros | Cons | Why not |
|---|---|---|---|
| Bounded sync/async fan-out with stable join (chosen) | Improves latency, preserves deterministic output shape, no dependency | Worker code must tolerate concurrent execution | Best fit for the existing team API |
| Keep serial execution | Simplest scheduling semantics | Leaves independent delegation unnecessarily slow | Does not meet the runtime parity goal |
| Unbounded thread/task creation | Highest apparent parallelism | Resource exhaustion and unpredictable host load | Unsafe default for a framework runtime |
| Add a distributed task broker | Cross-process scale and durability | New external state, deployment, and dependency contract | Defer to a separately reviewed distributed execution slice |

## Consequences

- Positive: independent supervised workers and consensus members can overlap,
  with a configurable bounded concurrency budget.
- Positive: sync-only and native-async agents share one orchestration contract;
  result ordering remains deterministic.
- Negative / debt accepted: this is in-process concurrency, not a distributed
  scheduler or hard sandbox. Team-wide cancellation and per-member budgets
  remain follow-on capabilities.
- Invalidation triggers: cross-process execution, durable fan-out recovery, or
  a requirement to coordinate shared mutable agent state.
