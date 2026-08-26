# ADR-032: Unified bounded agent-run lifecycle events

**Date:** 2026-08-26  
**Status:** accepted  
**Deciders:** Chief Architect

## Context

MAPLE already has a bounded, redacting `EventStream`, but autonomous sync and
async runs did not publish a common lifecycle. Hosts had to infer model/tool
progress from provider-specific logs, and there was no standard usage trailer
for a completed run. Current agent frameworks make run/event inspection a core
developer surface; MAPLE needs the local contract before considering hosted
telemetry or exporter integrations.

## Decision

Add an opt-in `AutonomousAgent.set_event_stream()` attachment. Both sync and
async ReAct loops publish the same metadata-only lifecycle events using the
existing `EventStream` bounds and redaction policy:

- `run.started` or `run.resumed` with status and step cursor;
- `model.response` with step, tool-call count, finish reason, duration, and
  prompt/completion/total usage;
- `tool.completed` with tool identity, error flag, and content length;
- `run.paused` with the bounded approval ID;
- `run.completed` with step count and a final usage trailer; and
- `run.failed` for maximum-step termination.

Raw prompts, model content, tool arguments, tool output, and final result data
are intentionally not included in these lifecycle payloads. Event publication
is best-effort telemetry: a rejected event is logged at debug level and does
not change the agent's execution result. The stream's bounded ring and
`dropped_count` provide the local retention/backpressure boundary; subscribers
must hand off blocking work to a host-owned queue.

## Alternatives considered

| Option | Pros | Cons | Why not |
|---|---|---|---|
| Reuse existing `EventStream` (chosen) | No dependency, existing redaction/bounds/sequence semantics | In-process only and best-effort delivery | Smallest safe public contract for local hosts |
| Emit full prompts, arguments, and results | Richer debugging | Credential/data leakage and larger payloads | Violates the metadata-only observability boundary |
| Add a hosted exporter or broker | Durable inspection and fan-out | Auth, tenancy, deployment, and cloud decisions | Deferred until local event semantics and provider target are approved |
| Make telemetry failure fail the run | Strong delivery signal | Observability outage becomes an agent outage | Runtime correctness must not depend on optional telemetry |

## Consequences

- Positive: sync and async runs expose the same ordered lifecycle vocabulary and
  bounded usage trailer.
- Positive: event payloads inherit recursive redaction, size limits, ring
  retention, subscriber isolation, and sequence numbers from `EventStream`.
- Negative / debt accepted: this is not durable telemetry, a hosted exporter,
  or a distributed backpressure protocol. Event eviction is observable through
  `dropped_count`.
- Negative / debt accepted: cancellation tokens, provider-native token streams,
  trace/span export, and durable event cursors remain separate capabilities.

