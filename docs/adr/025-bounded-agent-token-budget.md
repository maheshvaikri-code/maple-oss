# ADR-025: Bounded per-goal token accounting

**Date:** 2026-08-25
**Status:** accepted
**Deciders:** Chief Architect

## Context

MAPLE already exposes provider-level token usage in `LLMResponse` and decision
traces, but an autonomous goal had no aggregate usage record or hard budget.
Without a goal boundary, hosts could not reliably cap multi-step ReAct work
before a tool side effect.

## Decision

Add opt-in per-goal accounting through `Goal.token_usage` and
`AutonomousConfig.max_total_tokens`. Every reasoning and reflection response in
the synchronous and asynchronous ReAct loops contributes provider-reported
prompt, completion, and total tokens. A configured budget requires provider
usage data; missing or malformed usage fails closed. If the aggregate exceeds
the budget, the loop returns `TOKEN_BUDGET_EXCEEDED` before executing the
current response's tools.

The default remains `None`, preserving existing provider compatibility. The
budget applies to the ReAct goal loop and its reflection calls; standalone
`decompose_goal` calls remain outside that loop boundary.

## Alternatives considered

| Option | Pros | Cons | Why not |
|---|---|---|---|
| Opt-in provider-backed goal budget (chosen) | Deterministic host control, no dependency, sync/async parity | Providers must report usage when a budget is configured | Best compatible boundary for the current provider contract |
| Estimate tokens locally | Works without provider metadata | Model/tokenizer drift makes hard enforcement unreliable | Not safe as a hard budget |
| Enforce only provider `max_tokens` | Simple provider parameter | Caps one response, not the complete multi-step goal | Does not bound agent work |
| Add a cost/billing service | Rich accounting and currency support | External state, credentials, and provider coupling | Defer to a host-level integration |

## Consequences

- Positive: hosts can inspect aggregate per-goal usage and fail closed before
  tool execution crosses a configured token budget.
- Positive: reflection calls are included, and synchronous/asynchronous loops
  share the same accounting boundary.
- Negative / debt accepted: provider usage is required only when a budget is
  configured; no cost conversion or external billing integration is claimed.
- Invalidation triggers: provider contracts stop returning usage, a need for
  multi-goal/team budgets, or a reviewed cost accounting surface.
