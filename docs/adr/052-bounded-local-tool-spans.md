# ADR-052: Bounded local tool spans under model-step parents

**Date:** 2026-08-26  
**Status:** accepted  
**Deciders:** Chief Architect

## Context

Slice 105 records model-step spans and links them to metadata-only model
events and decision traces, but tool execution remains visible only through
completion events. Agent tool calls may be synchronous or asynchronous,
approval-gated, human-input-producing, successful, or failed. The local
recorder must add useful parent/child timing without persisting arguments,
results, or provider objects, and without changing run outcomes.

## Decision

We will create an optional bounded `agent.tool` span for each normal tool
execution, using the open model-step span as its parent and the model step's
trace ID as the correlation boundary. The span will retain only bounded tool
identity, step, error flag, and serialized result length; it will finish on
success or typed tool failure, and telemetry failures will remain isolated
from agent behavior. Approval replays and other host-invoked tool execution
continue to use their existing path until a host-owned trace context is
available.

## Alternatives considered

| Option | Pros | Cons | Why not |
|---|---|---|---|
| Local child spans (chosen) | Preserves hierarchy, timing, and provider-neutral local behavior | Does not deliver or aggregate remotely | Fits the current recorder boundary and can be tested without external services |
| Add IDs only to `tool.completed` events | Small implementation | No duration or parent/child span data | Insufficient for tool latency/error analysis |
| Add OpenTelemetry/exporter integration now | Broad ecosystem compatibility | New dependency/transport/configuration and secret/data-governance surface | Deferred until dependency and hosted-exporter policy is explicitly approved |

## Consequences

- Positive: normal tool latency and bounded outcome metadata become visible in
  the same local trace as the model step, for both sync and async loops.
- Negative / debt accepted: approved-tool replay, remote export, sampling,
  backpressure metrics, and exactly-once effect correlation remain host-owned
  follow-ups.
- Invalidation triggers: a hosted observability requirement, a need to trace
  approval replays across processes, or a requirement for exporter-level
  sampling/backpressure would reopen this local-only decision.
