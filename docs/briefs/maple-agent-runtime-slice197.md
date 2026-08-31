# Slice 197 brief - offline provider contract fixtures

**Date:** 2026-08-29
**Class:** L (cross-provider public runtime boundary and release evidence)
**Requested by:** human continuation request

## Problem

MAPLE's OpenAI-compatible and Anthropic providers expose the same public LLM
contract, but their completion payload mappings and model-response parsers are
not covered by a complete, provider-specific offline fixture set. Provider SDK
or response-shape drift could therefore escape local verification, and
malformed tool arguments could cross the model boundary as executable input.

## Scope

- In: deterministic fake-SDK fixtures for OpenAI-compatible and Anthropic sync
  and async completion; tool, system, stop, usage, and image payload mapping;
  response parsing and usage assertions; fail-closed malformed tool-argument
  handling; provider error classification fixtures.
- **Non-goals:** live provider calls, credentials, model/prompt changes,
  automatic provider discovery, hosted routing, health/load balancing, or
  distributed state.
- Deferred: broader provider catalogs, provider-owned judge/calibration
  services, native SDK version matrices, and live contract tests.

## Acceptance criteria

1. Given a deterministic OpenAI-compatible fake client, when sync and async
   completion receives text, tool-call, usage, stop, and multimodal input,
   then MAPLE sends the documented payload and returns the normalized
   `LLMResponse` with bounded usage and tool arguments.
2. Given a deterministic Anthropic fake client, when sync and async completion
   receives system, text, tool, usage, stop, and image input, then MAPLE sends
   the documented Messages payload and returns the normalized response.
3. Given malformed JSON tool arguments or a non-object decoded argument value,
   when a provider response is parsed, then MAPLE returns a typed
   `LLM_PROVIDER_RESPONSE_INVALID` error and no tool-call arguments are exposed
   for execution.
4. Given malformed or out-of-range provider usage metadata, when a completion
   response is parsed, then MAPLE returns a typed response error without
   mutating usage counters.
5. Given transient, non-transient, and raised provider failures, when the
   provider boundary handles them, then exact error classification and
   fail-closed `Result` behavior remain stable.
6. The fixture suite runs without network access or new dependencies, the
   public import/example remains valid, and the complete repository suite stays
   green.

## Constraints

- Preserve the existing `LLMProvider`/`Result` contract and Python support
  range declared by `pyproject.toml`.
- No SDK installation or network access; fake clients must be local,
  deterministic, and bounded.
- Model output is untrusted: tool arguments and usage are validated before
  they reach MAPLE execution or accounting state.
- Existing user-owned changes remain outside this slice.

## Assumptions (chosen defaults - correct me if wrong)

- A malformed tool-call argument is a provider-response error, not an empty
  argument object that might accidentally invoke a tool.
- Provider usage fields are non-negative integers; prompt/input and
  completion/output fields are required when usage is present, total usage is
  derived when omitted, and a missing usage object means usage is unavailable.
  A present malformed usage object is rejected.
- The existing OpenAI-compatible and Anthropic payload shapes are the target
  contracts; no live SDK version upgrade is implied.

## Open questions (blocking - answered before G1)

- None for this offline local slice. Hosted/provider-version decisions remain
  separate human-gated work.

**Human confirmed:** yes - standing continuation request on 2026-08-29
