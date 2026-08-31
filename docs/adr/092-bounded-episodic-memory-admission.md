# ADR-092: Bounded Episodic-Memory Admission

## Status

Accepted for preview release readiness.

## Context

`EpisodicMemory.record()` stored an ever-growing list under each task key and
silently treated state-read failures as an empty history. An oversized or
malformed event could therefore reach persistence, and an unreadable existing
record could be replaced. Agent memory needs a finite local boundary that
preserves the newest useful events while making failures observable.

## Decision

Add bounded admission to `EpisodicMemory`:

- task IDs are non-empty UTF-8 text without Unicode control characters and at
  most `256` UTF-8 bytes;
- `max_events_per_task` defaults to `1,024` and cannot exceed that value;
- `max_event_bytes` defaults to `65,536` and cannot exceed that value;
- events must be mappings and the event plus timestamp must serialize as
  finite UTF-8 JSON within the configured byte bound;
- an accepted record retains the newest `max_events_per_task` events;
- malformed input returns a typed error before any store access; store read,
  write, and malformed-state errors are returned rather than hidden.

The bounded contract is local to the `EpisodicMemory`/`StateStore` instance.
It does not coordinate quotas across processes or stores.

## Alternatives considered

| Alternative | Reason not selected |
|---|---|
| Keep unbounded per-task histories | It allows persistent memory growth to follow caller traffic indefinitely. |
| Reject new events when a task history is full | It loses current events even when bounded newest-window retention is safe and useful. |
| Replace unreadable state with a fresh history | It hides corruption/read failures and can destroy recoverable evidence. |
| Retain a newest bounded window after reject-before-write validation | Selected: bounds local growth, preserves recent context, and keeps malformed/oversized records out of persistence. |

## Consequences

Positive consequences:

- Per-task event history and individual serialized records have explicit caps.
- Newest accepted events remain available without unbounded list growth.
- Invalid records and malformed state fail closed with stable error types.
- Existing `EpisodicMemory(store)` construction remains compatible through
  bounded defaults.

Negative consequences and boundaries:

- Older events are intentionally evicted once the per-task count is full.
- The quota is not a distributed global memory budget and does not bound the
  number of task keys in a store.
- The serialization boundary uses a deterministic local size check; it is not
  a model tokenizer, semantic index, summarizer, or billing estimate.
- No retry, transaction, rollback, or automatic summarization is introduced.

## Failure modes

`EPISODIC_TASK_ID_INVALID`, `EPISODIC_EVENT_INVALID`,
`EPISODIC_EVENT_TOO_LARGE`, and `EPISODIC_STATE_INVALID` identify local
validation/state failures. Existing `StateStore` errors are propagated. No
invalid or oversized record causes a store write.

## Evidence

Focused memory regressions cover constructor limits, newest-window retention,
oversized-event rejection without a write, invalid task/event data, and the
existing record/recall integration. Full release evidence is recorded in the
slice 147 QA and review records.
