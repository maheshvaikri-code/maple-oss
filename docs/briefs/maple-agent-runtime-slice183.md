# Project/Task Brief - Bounded remote event and trace search

**Date:** 2026-08-28 - **Class:** M (observability transport increment) - **Requested by:** human

## Problem

MAPLE's authenticated event transport can publish and cursor-read retained
redacted events, but remote operators must currently retrieve the whole
retained window and filter it locally. That makes bounded run/trace diagnosis
awkward and needlessly increases response volume.

## Scope

- In: add exact-filter search over the existing retained `EventStream`.
- In: support `trace_id`, `run_id`, and `event_type` filters, bounded by the
  existing event retention and response limits.
- In: expose the search through authenticated `RunServer`/`RunClient` event
  transport under the existing `event:read` scope.
- In: preserve event redaction, cursor-expiry behavior, deterministic sequence
  order, and typed input errors.
- **Non-goals:** hosted aggregation, fleet-wide search, distributed indexes,
  arbitrary payload queries, regex/filter expressions, or changes to event
  retention.

## Acceptance criteria

1. At least one exact filter is required; unsupported or duplicate query keys
   fail closed with a typed error.
2. `trace_id` matches only the redacted event payload's top-level `trace_id`
   value; `run_id` and `event_type` use exact matching.
3. Search results are bounded, sequence-ordered, redacted, and preserve
   `EVENT_CURSOR_EXPIRED` behavior for an evicted `after_sequence`.
4. HTTP search uses `event:read`; unauthorized or insufficiently scoped callers
   do not inspect the stream.
5. Existing publish/read APIs and all compatibility tests remain green; no
   hosted or distributed search claim is added.

## Constraints

Stdlib only; reuse `EventBatch`, `EventCursor`, event validation, response
bounds, and the existing `Result`/error surfaces. Search must inspect only
retained events and must never expose unredacted payloads.

**Human confirmed:** no - bounded observability increment recorded for review
