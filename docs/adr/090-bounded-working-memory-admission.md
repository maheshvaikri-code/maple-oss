# ADR-090: Bounded Working-Memory Admission

## Status

Accepted for preview release readiness.

## Context

`WorkingMemory` is an in-process context helper used by autonomous agents.
Its prior admission boundary accepted arbitrary entry counts and estimated
content size, which allowed unbounded metadata growth and did not distinguish
an entry that could never fit from an entry that should evict older context.
The memory API also needed typed, non-mutating failures for malformed text and
relevance metadata.

## Decision

Keep the existing in-memory API and add a bounded admission contract:

- `max_tokens` must be an integer from `1` through `1,000,000`.
- At most `4,096` entries are retained.
- Keys must be non-empty text without control characters and at most `256`
  UTF-8 bytes.
- Content must be text that can be encoded as UTF-8.
- Relevance must be a finite number in the inclusive range `0..1`.
- Estimated tokens are `ceil(UTF-8 byte length / 4)`, with empty content using
  zero tokens. This is a deterministic local bound, not a model tokenizer.
- An accepted entry evicts oldest entries until both token and count budgets
  are satisfied. An entry larger than the entire token budget is rejected
  before any eviction or append.

Invalid inputs return typed `Result.err` values with stable `errorType`
identifiers. Rejected input never mutates the existing entries or token usage.

## Alternatives considered

| Alternative | Reason not selected |
|---|---|
| Keep unbounded legacy admission | It leaves memory and metadata growth dependent on caller behavior. |
| Add a model-specific tokenizer dependency | It would add dependency and model-version coupling for a local safety bound. |
| Add automatic summarization or managed context windows | It changes content semantics and requires provider, persistence, and policy decisions beyond this local contract. |
| Add deterministic bounded admission with a local UTF-8 estimate | Selected: bounded, dependency-free, predictable, and compatible with existing oldest-entry eviction. |

## Consequences

Positive consequences:

- Memory growth is bounded by entry count and estimated UTF-8 content size.
- Malformed or hostile text fails closed before state mutation.
- Existing callers retain oldest-entry eviction for entries that can fit.
- Error types give hosts a stable way to distinguish invalid metadata from an
  entry that is too large.

Negative consequences and boundaries:

- The estimate can differ from a provider's tokenizer and is not a billing or
  context-window guarantee.
- This slice does not summarize, persist, share, or automatically compact
  memory; those remain host-owned capabilities.
- `WorkingMemory` remains an in-process helper and is not thread-safe. Hosts
  sharing one instance across threads must provide external synchronization.
- The entry count cap applies to accepted entries and may evict the oldest
  entry even when token usage alone would fit.

## Failure modes

The public failure identifiers are `MEMORY_KEY_INVALID`,
`MEMORY_CONTENT_INVALID`, `MEMORY_RELEVANCE_INVALID`, and
`MEMORY_ENTRY_TOO_LARGE`. Constructor budget violations raise `ValueError`.
No failure path performs eviction or appends a new entry.

## Evidence

Focused working-memory regressions cover budget validation, UTF-8 accounting,
entry-size rejection without eviction, count bounds, invalid metadata, and
Unicode edge cases. Full release evidence is recorded in the slice 145 QA and
review records.
