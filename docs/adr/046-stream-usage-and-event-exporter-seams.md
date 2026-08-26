# ADR-046: Bounded stream usage and event exporter seams

**Date:** 2026-08-26  
**Status:** accepted  
**Deciders:** Chief Architect, Backend, Security

## Context

MAPLE has provider-native OpenAI-compatible and Anthropic stream adapters and
a bounded in-process `EventStream`, but the two contracts did not expose
provider correlation or final usage trailers. Observability consumers also
had to subscribe directly and build their own delivery boundary. Usage and
telemetry must remain bounded and must not make an agent run fail.

## Decision

Extend `LLMChunk` with optional `TokenUsage` and a bounded provider
`request_id`. Native providers normalize their final stream usage into one
trailer and track it in provider usage statistics. OpenAI-compatible clients
opt into the provider's usage request with
`LLMConfig.extra["include_stream_usage"] = True`; Anthropic input/output usage
events are merged. Missing or malformed usage is omitted instead of guessed.
The completion-backed base stream forwards completion usage and request ID
when already available.

Add an optional host-owned `EventExporter` to `EventStream`. The exporter
receives the already-redacted, bounded `AgentEvent` after retention and
subscriber delivery. Exporter configuration is validated, and exporter
exceptions are isolated so telemetry cannot change the run result. The seam
is synchronous and local; queueing, persistence, retry, and remote transport
remain host responsibilities.

## Alternatives considered

| Option | Pros | Cons | Why not |
|---|---|---|---|
| Optional bounded fields and exporter protocol (chosen) | Additive, dependency-free, preserves current consumers and redaction | Does not provide hosted delivery or full trace spans | Smallest useful linkage/export seam |
| Copy raw provider objects into chunks | Maximum provider detail | Leaks SDK-specific and potentially sensitive payloads | Violates the normalized public contract |
| Make telemetry export mandatory | Strong delivery guarantee | Couples agent success to an external sink | Observability must be non-blocking and non-authoritative |
| Add a durable exporter queue | Reliable delivery | New storage/retry/ownership contract | Requires a separately approved hosted/distributed design |

## Consequences

- Positive: stream consumers can correlate a provider response and account for
  final usage without depending on SDK object shapes.
- Positive: hosts can connect redacted lifecycle events to their own bounded
  queue or logger without replacing `EventStream` subscribers.
- Negative / debt accepted: provider chunks are not yet automatically linked
  into `AutonomousAgent` lifecycle events or a trace/span graph. The exporter
  is synchronous and does not promise delivery, retry, durability, or remote
  authentication.
- Negative / debt accepted: stream iteration remains cooperative; hard
  cancellation and exactly-once external effects are not claimed.

