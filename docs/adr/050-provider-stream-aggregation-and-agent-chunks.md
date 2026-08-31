# ADR-050: Provider Stream Aggregation and Agent Chunk Events

- Status: Accepted
- Date: 2026-08-26
- Decision owners: Chief Architect, Backend, Security, QA

## Context

MAPLE already exposes provider-native OpenAI-compatible and Anthropic async
streams through `LLMChunk`, but autonomous ReAct execution consumed only the
final `LLMResponse`. That left hosts without one bounded way to reconstruct a
streamed response or observe model progress alongside tool and run events.
Provider chunks can contain prompt-adjacent data, partial JSON arguments, and
SDK-specific objects, so forwarding them directly into the lifecycle stream
would widen the public data and security boundary.

## Decision

Add `LLMProvider.complete_from_stream`, an async provider-base helper that:

- consumes the shared `LLMChunk` contract and reconstructs text, tool calls,
  finish reason, usage, model, and safe request correlation into `LLMResponse`;
- supports fragmented JSON tool arguments and providers that identify a new
  tool call by ID rather than by index;
- enforces bounded content, chunk, tool-call, argument, finish-reason, and
  request-ID quotas and returns typed errors for malformed streams;
- invokes an optional synchronous callback only after chunk validation;
- isolates callback failures and provider exceptions, and never copies raw SDK
  response objects into the aggregate response.

Add `AutonomousConfig.stream_model_events`, defaulting to `False`. When true,
sync and async ReAct model steps use the collector and publish a `model.chunk`
event for each chunk. These events contain only bounded metadata: step number,
content byte count, tool-call presence, finish/usage metadata, and a safe
provider request ID. Content, partial arguments, prompts, tool outputs, and
final result data remain outside this event contract. The default path is
unchanged for compatibility.

## Alternatives considered

1. Publish raw provider chunks. Rejected because SDK objects and partial tool
   arguments would become an accidental public and persistence boundary.
2. Make all autonomous runs streaming by default. Rejected because it changes
   provider invocation behavior and can surprise existing hosts.
3. Add a hosted event transport or tracing backend. Deferred; transport,
   exporter delivery, trace/span graphs, and backpressure telemetry remain
   host-owned or separate reviewed slices.

## Consequences

Hosts can opt into a uniform local progress signal while retaining the normal
completion response and error semantics. Native providers gain multi-tool
stream reconstruction even when an API omits an explicit index but supplies a
new tool-call ID. The collector is intentionally local and bounded: it does
not provide remote streaming, exactly-once delivery, hard cancellation,
backpressure guarantees, or semantic trace/span export.

## Validation

The slice includes provider aggregation tests for fragmented text/tool calls,
usage and request trailers, quota failure, and ID-based multi-tool assembly,
plus sync/async agent lifecycle tests proving metadata-only `model.chunk`
events. Full release-gate evidence is recorded in `docs/qa.md` and
`docs/review.md` after the final tracked-suite and package audit.
