# ADR-141: Offline provider contract fixtures and fail-closed response parsing

**Date:** 2026-08-29
**Status:** accepted for the scoped local preview contract
**Deciders:** Chief Architect

## Context

MAPLE already provides OpenAI-compatible and Anthropic adapters behind a common
`LLMProvider` interface. Native streaming fixtures exist, but completion
payload/response contracts are less comprehensively exercised offline. Provider
responses are untrusted model output: malformed tool arguments or usage fields
must not be turned into tool input or accounting state by a permissive parser.

## Decision

We will add deterministic fake-client fixtures for both providers' sync and
async completion paths and harden their response parsers to reject malformed
tool-call arguments and malformed usage metadata with a typed
`LLM_PROVIDER_RESPONSE_INVALID` error. Missing usage remains an explicit
unavailable value. The fixture boundary will not install SDKs, perform network
calls, or claim live provider-version compatibility.

## Alternatives considered

| Option | Pros | Cons | Why not |
|---|---|---|---|
| Offline fake-client contracts plus shared validation (chosen) | Deterministic, no credentials/network, catches mapping and trust-boundary regressions | Does not prove live SDK versions | Best local evidence with no external dependency or paid service |
| Live provider contract tests | Proves deployed endpoints and SDK behavior | Requires credentials, network, quota, data policy, and unstable external state | Not suitable for local release gates or this human-authorized scope |
| Keep permissive parsers and rely on tool schemas | Minimal code change | Malformed model output can reach execution or poison usage accounting | Fails closed only after the unsafe boundary has already been crossed |

## Data flow and failure boundary

```text
fake/provider SDK response
          |
          v
provider parser -- malformed JSON/non-object args --> typed response error
          |
          +-- malformed usage ---------------------> typed response error
          |
          v
validated LLMResponse + optional validated TokenUsage
          |
          v
Result boundary / caller-owned tool execution
```

## Consequences

- Positive: both provider completion contracts become runnable offline; bad
  tool input and usage values fail before execution/accounting; no dependency
  or credential surface grows.
- Negative / debt accepted: fake SDK objects cannot prove live service or SDK
  version compatibility; a provider-specific fixture must be updated when a
  supported response shape changes.
- Invalidation triggers: a live compatibility guarantee, additional provider
  families, audio/video output, streaming failover, or provider-owned judging
  would require a new scope and dependency/privacy review.
