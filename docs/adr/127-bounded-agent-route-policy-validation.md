# ADR-127: Validate AgentRegistry route allowlists at the public boundary

**Date:** 2026-08-28 - **Status:** proposed
**Deciders:** Chief Architect (public local routing contract)

## Context

Slice 180 added exact agent allowlists to Principal and passes the validated
tuple into AgentRegistry.route. AgentRegistry.route is also public and accepts
allowed_agent_ids directly. Its current set conversion trusts arbitrary
iterables, allowing malformed values to raise TypeError or produce ambiguous
policy behavior outside the server path.

## Decision

Normalize allowed_agent_ids inside AgentRegistry.route before reading the
registry. Reject strings/bytes, invalid identifiers, duplicates, and values
over the existing agent bound with a typed AGENT_ALLOWLIST_INVALID error.
Return the validated exact set for candidate filtering. None remains
unrestricted; an empty tuple remains a valid allowlist that selects no agent.
No handler is called when normalization fails.

## Alternatives considered

| Option | Pros | Cons | Why not |
|--------|------|------|---------|
| Validate at AgentRegistry.route (chosen) | Covers direct and server callers with one boundary | Adds a small normalization cost | The public method must not trust only one caller |
| Rely on Principal validation | No route code change | Direct callers remain unsafe and inconsistent | Does not cover the public registry API |
| Let set conversion raise | Minimal code | Untyped failure and possible policy ambiguity | Violates fail-closed typed error handling |

## Consequences

- Positive: malformed route policy becomes deterministic, typed, and handler-free.
- Negative / debt accepted: the allowlist remains static and exact; it does
  not add wildcard or dynamic policy.
- Invalidation triggers: a new shared policy object or a different agent
  identity model that makes current identifier bounds insufficient.
