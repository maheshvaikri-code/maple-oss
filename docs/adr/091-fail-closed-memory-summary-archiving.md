# ADR-091: Fail-Closed Memory Summary Archiving

## Status

Accepted for preview release readiness.

## Context

`MemoryManager.summarize_and_archive()` asks a caller-owned LLM provider for a
summary, writes that summary to episodic memory, and clears working memory.
The previous implementation ignored the episodic write result and cleared the
working context even when persistence failed. That behavior could silently
lose the source context and made retry or operator inspection impossible.

## Decision

Treat the operation as an ordered two-step boundary:

1. Return the provider error unchanged if completion fails.
2. Attempt the episodic archive and return its typed error unchanged if it
   fails.
3. Clear working memory only after the archive returns `Result.ok`.
4. Return the generated summary after the clear succeeds.

Empty working memory retains its existing successful no-op behavior. The
operation remains explicit and caller-invoked; it does not add retries,
automatic summarization, or a new persistence dependency.

## Alternatives considered

| Alternative | Reason not selected |
|---|---|
| Clear working memory before archiving | Risks irreversible context loss when the store rejects or fails. |
| Ignore the archive result as before | Hides persistence failure and makes a successful return misleading. |
| Add a cross-store transaction or rollback protocol | Requires coordination across provider output, working memory, and episodic storage beyond this local API. |
| Archive first and clear only after success | Selected: preserves the source on failure and is compatible with the existing `Result` contract. |

## Consequences

Positive consequences:

- Persistence failures are observable through the existing typed result.
- Working context remains available for inspection or an explicit retry.
- Successful behavior and the empty-memory no-op remain compatible.
- No dependency or storage protocol change is required.

Negative consequences and boundaries:

- A failed archive can leave the same context available for repeated calls;
  hosts must choose their retry and deduplication policy.
- The provider completion and episodic write are not one atomic transaction.
  A process failure after the write and before the clear may produce a durable
  summary while retaining working entries.
- This ADR does not assess summary quality, redact provider output, or provide
  managed/distributed memory.

## Failure modes

Provider failures retain the existing provider error. Episodic failures return
their existing typed error and do not clear working memory. No failure path
claims that external side effects or cross-store writes are exactly once.

## Evidence

Focused memory regressions verify that an episodic archive error is returned
and the working context and token usage remain intact. Full release evidence is
recorded in the slice 146 QA and review records.
