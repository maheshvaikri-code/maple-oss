# ADR-009: Provider-agnostic LLM stream contract

**Date:** 2026-08-24
**Status:** accepted
**Deciders:** Chief Architect, ML Engineer

## Context

`LLMChunk` and capability declarations exist, but the base
`LLMProvider.stream()` always returns `NOT_IMPLEMENTED`. That prevents agent
consumers from using one stable stream interface with providers that only
expose a completion API. A compatibility stream is useful for UI/event
consumers, but it must not be described as low-latency network token streaming
when the provider has not implemented that transport.

## Decision

We will make the base provider stream contract usable by completing one
request, then yielding bounded text chunks, complete tool-call deltas, and a
final finish chunk. Provider implementations may override this method for
native network streaming. The fallback preserves `Result` errors from the
completion call, uses a fixed 256-character chunk bound, and does not change
provider capability declarations: callers must still declare `streaming=True`
only when their provider supports the required streaming semantics.

## Alternatives considered

| Option | Pros | Cons | Why not |
|--------|------|------|---------|
| Completion-backed fallback with override seam (chosen) | Works with every existing provider, deterministic tests, no dependency change | First token waits for completion; not native network streaming | — |
| Keep `NOT_IMPLEMENTED` | No semantic ambiguity | Every consumer needs provider-specific branching and the shared API remains unusable | Fails the common stream contract |
| Implement SDK-specific OpenAI and Anthropic streams now | Lower first-token latency for two providers | Vendor SDK/version coupling, untested network behavior, separate error semantics | Defer to provider-specific slices with captured stream fixtures |

## Consequences

- Positive: agents and UI/event consumers can consume a uniform async iterator;
  text, tool-call, and finish events are represented by existing `LLMChunk`;
  completion failures remain typed `Result` errors.
- Negative / debt accepted: fallback latency is completion latency and usage
  is completion-level, not per-token. Native provider streams, cancellation,
  and backpressure remain provider/host-owned follow-up boundaries; native
  providers may expose a final usage trailer through `LLMChunk`.
- Invalidation triggers: a caller requires first-token latency, token-level
  cancellation, provider-native usage events, or a capability router that
  cannot distinguish fallback streams from native streams.
