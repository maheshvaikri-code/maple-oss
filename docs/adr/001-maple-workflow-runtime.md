# ADR-001: Native, Dependency-Free Workflow Runtime Boundary

**Date:** 2026-08-24  · **Status:** accepted  · **Deciders:** Chief Architect

## Context

MAPLE's autonomous layer currently provides a ReAct loop and two orchestration
patterns, while its state stores provide storage primitives. It does not have a
first-class workflow graph, run identity, checkpoint contract, or resumable
execution model. These capabilities are foundational for human approval,
replay, event streaming, and agent evaluation.

The repository is a library with a stdlib-first dependency policy. A workflow
runtime must preserve existing MAPLE `Result<T,E>` behavior, remain usable with
the current Python support range, and avoid making a third-party framework a
hard runtime dependency.

## Decision

We will add a native workflow boundary in `maple.autonomy.workflow` using
small typed dataclasses, a validated directed graph, and a checkpoint-store
protocol. The initial implementation will support deterministic sequential
execution, explicit conditional routing, stable run IDs, checkpoint writes at
node boundaries, interruption state, and resume from the last committed node.
The checkpoint boundary will accept serializable state snapshots and will be
adaptable to MAPLE's existing `StateStore`; it will not use pickle or execute
arbitrary code during restore.

The runtime will own workflow state and run lifecycle. Existing agents,
brokers, tools, and state stores remain dependencies of the runtime, not
co-owners of mutable workflow state. Parallel execution, external workers,
and hosted persistence are follow-on slices after the sequential contract is
tested.

## Alternatives considered

| Option | Pros | Cons | Why not |
|--------|------|------|---------|
| Native MAPLE graph + checkpoint ports (chosen) | No new runtime dependency; fits `Result<T,E>` and existing state stores; public contracts remain MAPLE-owned | More implementation and testing work | Chosen for control, portability, and a small reversible first slice |
| Embed LangGraph as the runtime | Mature graph and checkpoint features | Adds a large framework dependency and couples MAPLE's public API to another runtime | Interoperability remains valuable, but MAPLE should not require LangGraph |
| Extend `AgentOrchestrator` directly | Small initial diff | Mixes team coordination with workflow state, making resume/replay and future routing harder to isolate | Existing orchestrator remains a compatibility layer |
| Do nothing / adapters only | Lowest short-term effort | Does not provide native parity or a stable MAPLE workflow contract | Fails the brief |

## Consequences

- Positive: a dependency-free, testable foundation for durable agent runs;
  existing storage backends can be reused; failures are explicit at a single
  boundary; later features can compose around a stable run contract.
- Negative / debt accepted: the first slice is sequential and local; parallel
  execution, hosted persistence, and a visual workflow surface remain later
  work.
- Invalidation triggers: a required supported Python feature unavailable in
  the declared range; measured checkpoint latency or state size exceeding the
  release budget; or a human decision to make a third-party workflow runtime
  the supported public API.
