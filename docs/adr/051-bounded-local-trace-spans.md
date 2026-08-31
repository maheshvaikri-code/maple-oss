# ADR-051: Bounded Local Trace Spans for Agent Model Steps

**Date:** 2026-08-26 · **Status:** accepted  
**Deciders:** Chief Architect, Backend, Security, QA

## Context

MAPLE has bounded lifecycle events and decision traces, but no local span
record that lets a host correlate a model step's chunks, final response, and
decision trace without adopting a tracing backend. The runtime must preserve
the existing no-dependency and fail-closed posture while making progress toward
the observability surfaces present in leading agent frameworks.

Threat sketch: assets are prompts, tool arguments, provider IDs, and host
telemetry; entry points are span attributes and agent model-step metadata. The
worst plausible abuse is unbounded or secret-bearing attributes turning a
diagnostic recorder into a data-exfiltration or memory-amplification sink.

## Decision

We will add a thread-safe bounded `SpanRecorder` and immutable `TraceSpan`
contract in the existing observability module. Span names and IDs are bounded,
attributes are recursively redacted then restricted to at most 32 flat JSON
scalars and 16 KiB, records retain newest-first within a configurable cap of
1–100,000, and invalid transitions return typed `Result` errors. An agent may
opt into the recorder with `set_span_recorder`; each ReAct model step receives
one span whose trace/span IDs are copied into `model.chunk`, `model.response`,
and `DecisionTrace` metadata. Span recording is observational: recorder
failures never change the model or tool outcome, and the recorder does not
export or persist remotely.

## Alternatives considered

| Option | Pros | Cons | Why not |
|---|---|---|---|
| Local bounded recorder (chosen) | No dependency, inspectable, deterministic, host can export later | Not a hosted trace backend; retention is local | Matches current local-first release boundary |
| Adopt OpenTelemetry SDK now | Broad ecosystem compatibility and exporters | New dependency, configuration/security surface, version and transport policy | Deferred until a provider-neutral exporter contract and dependency review exist |
| Keep only `DecisionTrace`/events | No code or API surface change | No span identity/lifecycle or parent-child contract | Does not close the local correlation gap |

## Consequences

- Positive: hosts can correlate model chunks, final responses, and decisions by
  bounded IDs and inspect completed/error/cancelled local spans.
- Negative / debt accepted: only model-step spans are integrated; tool spans,
  durable/remote exporters, sampling, queue backpressure, and hosted trace
  search remain separate boundaries.
- Invalidation triggers: a required hosted exporter, distributed trace
  propagation, or tool-level span semantics reopens this ADR with a new
  dependency/security and transport decision.

