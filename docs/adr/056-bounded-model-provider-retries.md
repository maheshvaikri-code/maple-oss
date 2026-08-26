# ADR-056: Bounded Model/Provider Retries

- Status: Accepted
- Date: 2026-08-26
- Decision owners: Chief Architect, Backend, Security, QA

## Context

MAPLE's provider abstraction already returns typed `Result` errors, but the
autonomous ReAct loop previously treated every model failure as terminal. The
comparison runtimes make transient model failures easier to handle, while
retrying an authentication, validation, or malformed-request failure is both
unhelpful and potentially expensive.

The retry boundary must also preserve MAPLE's existing side-effect rule: a
model request happens before any tool calls for that step, so retrying a failed
model request must not replay a tool handler. Provider SDK exceptions must be
classified conservatively without exposing raw exception payloads in lifecycle
events.

## Decision

Add the opt-in `ModelRetryPolicy` configuration and apply it to the sync and
async autonomous model-completion boundary, including the bounded stream
collector path.

- `max_retries` is capped at three and defaults to zero, preserving fail-fast
  compatibility.
- `base_delay_seconds` and `max_delay_seconds` are finite, non-negative, and
  capped at 60 seconds. Exponential backoff is capped by the configured maximum.
- Only exact, configured `errorType` values are retryable. The default set is
  `LLM_RATE_LIMITED`, `LLM_TIMEOUT`, and `LLM_TRANSIENT_ERROR`.
- OpenAI-compatible and Anthropic adapters classify recognizable status codes
  and exception names. Unknown exceptions retain their operation-specific
  error type. Wrapped stream causes are inspected without copying exception
  messages into retry metadata.
- Each scheduled retry emits a metadata-only `model.retry_scheduled` event with
  the step, retry number, retry limit, delay, and bounded error type. Prompt,
  output, credentials, and raw provider objects are not emitted.
- A successful retry is accounted once, after the successful response returns.
  Failed requests do not execute tools or contribute provider usage unless the
  provider itself reports usage on that failed operation.

## Rejected alternatives

- Retrying every `Result.err` would retry permanent failures and hide useful
  operator feedback.
- Retrying inside tool execution would make external side effects ambiguous;
  tool idempotency remains a separate host-owned contract.
- A distributed retry scheduler, durable model retry queue, or exactly-once
  claim would require remote ownership, leases, and persistence contracts that
  are not part of this local slice.

## Consequences

Hosts can enable small, deterministic retry budgets for transient provider
conditions while retaining explicit fail-fast behavior by default. The policy
is public and dependency-free, but provider-specific status mapping remains
intentionally conservative and may require future adapter fixtures as SDKs
evolve. Remote transport, hosted retry coordination, circuit integration, and
provider-managed rate-limit scheduling remain follow-on work.
