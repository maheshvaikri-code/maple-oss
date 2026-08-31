# ADR-128: Add bounded exact-filter remote event search

**Date:** 2026-08-28 - **Status:** proposed
**Deciders:** Chief Architect (local event transport contract)

## Context

`EventStream` already retains a bounded, redacted event window and exposes
cursor reads through the authenticated `event:read` transport. Operators
diagnosing one run or trace currently need to read the window and filter it at
the client, even though the host already owns the retained event boundary.

## Decision

Add an exact-filter `EventStream.search()` operation and expose it as
`GET /v1/events/search` plus `RunClient.search_events()`. Accept one or more of
the bounded filters `trace_id`, `run_id`, and `event_type`; require at least one
filter; support `after_sequence` and a bounded result limit; and preserve
retained sequence order and cursor-expiry errors. A trace match reads only a
top-level `trace_id` string from the already-redacted event payload. The route
uses the existing `event:read` scope and returns the existing `EventBatch`
envelope.

Search remains a host-local retained-window query. It does not add arbitrary
payload expressions, regexes, indexes, fleet aggregation, hosted trace search,
or distributed consistency.

## Alternatives considered

| Option | Pros | Cons | Why not |
|--------|------|------|---------|
| Exact filters over retained events (chosen) | Small surface; reuses redaction, bounds, and cursor semantics | Linear scan of one bounded window | Correct local contract without an index or new dependency |
| Client-side filtering after `read_events` | No server change | Larger responses and poor operator ergonomics | Does not close the remote diagnostics gap |
| Arbitrary payload query language | Flexible | Large security/performance surface and possible data leakage | Outside the bounded observability contract |

## Consequences

- Positive: authenticated operators can retrieve bounded run/trace subsets
  without downloading unrelated retained events.
- Negative / debt accepted: each query scans the retained in-memory window;
  there is no index, cross-host aggregation, or durable search catalog.
- Invalidation triggers: event trace metadata moves out of the redacted
  top-level payload, or hosted search requirements receive an approved
  identity/tenancy/indexing design.
