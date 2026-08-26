# ADR-010: Provider-native LLM streaming adapters

**Status:** Accepted
**Date:** 2026-08-24

## Context

MAPLE exposes one async `LLMProvider.stream()` contract. The base provider
implementation intentionally uses a completion-backed fallback so callers can
consume bounded text, tool-call, and finish chunks even when a provider has no
native stream. Leading provider SDKs expose lower-latency server-sent event
streams, but their event shapes differ and the optional SDKs must remain
optional dependencies.

## Decision

Implement native stream overrides for the existing OpenAI-compatible and
Anthropic providers:

- OpenAI-compatible chat completion deltas map text, function-call fragments,
  and finish reasons into `LLMChunk` values.
- Anthropic Messages API events map text deltas, tool-use starts, partial JSON
  input, and normalized stop reasons into the same contract.
- Text deltas are split into the shared 256-character bound.
- Provider-final usage is normalized into a bounded `TokenUsage` trailer on
  `LLMChunk`, and provider request IDs are exposed when they are bounded and
  present. OpenAI-compatible usage requests are opt-in through
  `LLMConfig.extra["include_stream_usage"]`; Anthropic partial usage events
  are merged before the final trailer.
- Initial request failures return typed `Result.err` data; iteration failures
  raise a contextual runtime error because the request has already returned an
  async iterator.
- If an async provider client is unavailable, the provider preserves the base
  completion-backed fallback instead of making the optional SDK a hard runtime
  dependency.

The adapter shapes follow the providers' official streaming interfaces:
[OpenAI streaming](https://platform.openai.com/docs/guides/streaming) and
[Anthropic streaming](https://platform.claude.com/docs/en/build-with-claude/streaming).

## Alternatives considered

1. Keep only the completion-backed fallback. This is portable but does not
   provide first-token latency for the built-in providers.
2. Add a new streaming abstraction per provider. This would leak SDK event
   shapes to callers and fragment tool-call handling.
3. Make provider SDKs mandatory. This would expand the base install and break
   MAPLE's optional-provider boundary.

## Consequences

Positive:

- Built-in providers now provide real incremental text and tool-call output
  when their async SDK clients are available.
- Consumers retain one provider-agnostic async contract and bounded chunks.
- Offline tests can inject async iterators without credentials or network.

Accepted limitations:

- Runtime stream-iteration errors cannot be converted into a pre-iteration
  `Result.err` after chunks have already been delivered.
- Runtime stream usage is surfaced only when the provider emits usable usage
  fields; malformed or absent trailers are omitted rather than invented.
- Providers without async clients continue to use the completion-backed
  fallback and do not claim native latency.
