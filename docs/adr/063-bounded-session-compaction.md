# ADR-063: Bounded Host-Supplied Session Compaction

- Status: Accepted
- Date: 2026-08-26
- Decision owners: Chief Architect, Backend, Security, QA

## Context

MAPLE's bounded in-memory and file-backed session stores persist JSON-safe
conversation messages and replay only stored user/assistant messages into an
agent turn. A long-lived session can eventually reach its message or byte
quota, but automatic model summarization would add provider calls, hidden
mutation, prompt-injection risk, and an unclear failure boundary.

## Decision

Add an optional `SessionCompactionStore` contract implemented by the built-in
session stores:

- `compact(session_id, summary, keep_last=8, expected_version=None)` requires a
  non-empty host-supplied summary and an optimistic version when the caller
  has one.
- The summary is stored as one bounded assistant `SessionMessage` with
  `metadata.compaction="host_summary"`, the dropped-message count, and the
  source version. The requested recent tail is retained in order.
- Compaction is one atomic versioned store mutation. Stale versions, invalid
  limits, oversized summaries, missing sessions, and no-op requests return
  typed errors without changing the session.
- The runtime does not call an LLM, invent a summary, or compact sessions
  automatically. A host remains responsible for the summary's provenance and
  for protecting any sensitive content retained in the session store.
- `SessionStore` remains backward-compatible for custom stores; compaction is
  an optional capability that callers can detect through the separate
  `SessionCompactionStore` contract.

## Alternatives considered

| Option | Pros | Cons | Why not |
|---|---|---|---|
| Host-supplied bounded summary plus recent tail (chosen) | Deterministic, provider-neutral, explicit, and compatible with existing stores | Summary quality and provenance remain host responsibilities | Best local-first capability without hidden model work |
| Automatic LLM summarization | More convenient for callers | Adds provider cost/latency, prompt/data handling, and a new failure path | Not safe to introduce implicitly into a persistence API |
| Drop the oldest messages without a summary | Simple and bounded | Loses context silently and can break multi-turn behavior | Fails the context-preservation requirement |
| Store full history and bypass quotas | Preserves context | Unbounded memory/disk and denial-of-service exposure | Violates MAPLE's bounded-store contract |

## Consequences

- Positive: hosts can keep a bounded, inspectable conversation context across
  memory and file-store restarts while preserving CAS/version semantics.
- Negative / debt accepted: the summary is not independently verified for
  semantic faithfulness; token-aware automatic compaction, encrypted stores,
  and cross-process session leases remain separate capabilities.
- Invalidation triggers: a requirement for automatic provider summarization,
  token-budget-aware compaction, or semantic summary evaluation reopens this
  ADR before implementation.
