# ADR-088: Native Async Provider Completion

## Status

Accepted for preview release readiness.

## Context

MAPLE's asynchronous agent loop already exposes an asynchronous provider
contract, and the built-in providers already use native asynchronous clients
for streaming when those clients are available. Completion requests still
inherited the base implementation, which delegates to the synchronous
provider method. That compatibility behavior can block an event loop during a
normal async agent step.

## Decision

Implement `complete_async(...)` directly in the OpenAI-compatible and Anthropic
providers. Each adapter formats the existing bounded message/tool contract,
awaits its optional native SDK client, parses and tracks the normal
`LLMResponse`, and returns the existing classified error shape.

If an optional SDK does not provide an async client, the adapter delegates to
the base provider implementation. This preserves existing integrations while
making the fallback explicit in the public contract; the fallback is not
claimed to be non-blocking.

## Boundaries

This decision does not add retries, provider selection, concurrent fan-out,
background threads, or a new dependency. It does not make third-party
providers non-blocking unless their adapter implements the async contract.
Native async streaming and completion remain separate operations.

## Evidence

The provider regression suite uses offline async client fakes for both built-in
adapters and verifies awaited request formatting, stop controls, and parsed
responses. Full release evidence is recorded in the slice 143 QA and review
records.
