# ADR-047: Provider correlation in agent observability

**Date:** 2026-08-26  
**Status:** accepted  
**Deciders:** Chief Architect, Backend, Security

## Context

Slice 100 made provider request IDs available on native stream chunks and
`LLMResponse`, but an autonomous run's model lifecycle event and decision trace
did not carry that correlation. Hosts could observe usage and provider IDs only
at the provider boundary, making local troubleshooting and trace joins harder.

## Decision

When an `LLMResponse` contains a bounded request ID, `AutonomousAgent` copies it
as `provider_request_id` into the metadata-only `model.response` lifecycle
event and the corresponding `DecisionTrace`. `DecisionLogger.export_json()`
preserves the field. IDs longer than 256 characters or containing control
characters are omitted. No raw provider response or SDK object is copied.

This is additive and applies to both synchronous and asynchronous ReAct loops.
Provider stream chunks still expose their own request ID and usage trailer;
incremental chunk-to-run event aggregation and a full trace/span graph remain
separate work.

## Alternatives considered

| Option | Pros | Cons | Why not |
|---|---|---|---|
| Copy bounded ID into model metadata and decision trace (chosen) | Deterministic local joins; no provider object leakage; additive | Does not aggregate every stream chunk | Smallest useful run-level correlation boundary |
| Copy raw provider response metadata | Maximum detail | SDK-specific and potentially sensitive | Violates the redacted metadata contract |
| Add a full trace/span graph now | Richer observability | New lifecycle, sampling, storage, and exporter semantics | Requires a separate trace design |

## Consequences

- Positive: local event exporters, decision logs, and host traces can join a
  model response to the provider request that produced it.
- Positive: malformed or unbounded custom-provider IDs fail closed without
  changing the agent result.
- Negative / debt accepted: provider chunk events are not automatically
  emitted into the agent lifecycle stream, and no remote trace backend,
  durable exporter, sampling, or exactly-once telemetry delivery is claimed.

