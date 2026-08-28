# Project Brief - bounded agent capability discovery and routing

**Date:** 2026-08-28
**Class:** L - public registry metadata and authenticated transport route
**Requested by:** human

## Problem

The remote agent control plane currently requires callers to know an exact
agent ID. A host can register multiple agents, but it cannot expose bounded
capability metadata or select a registered agent by a declared capability.
`AutonomousAgentRemoteAdapter` also has no way to advertise the capabilities
of the native agent it binds. This limits remote multi-agent composition while
leaving routing policy implicit in callers.

## Scope

- In: bounded immutable `AgentDescriptor` metadata, optional capability
  registration, deterministic exact-match registry routing, and a metadata-only
  authenticated agent listing route.
- In: raw and typed `RunClient` routing methods plus native adapter capability
  registration.
- In: regressions, public API documentation, parity ledger, changelog, and
  release evidence.
- Non-goals: retries, failover, load balancing, health probing, queues,
  distributed scheduling, remote checkpoint transfer, identity federation,
  push notifications, or exactly-once side effects.

## Acceptance criteria (numbered, testable)

1. `AgentRegistry.register(..., capabilities=...)` validates bounded unique
   capability labels, retains legacy callers, and exposes detached descriptors
   sorted by agent ID without exposing handlers or run state.
2. An authenticated `GET /v1/agents` returns bounded descriptor metadata and
   fails closed for missing registry, unauthorized access, malformed state, and
   invalid registration input.
3. An authenticated `POST /v1/agent-routes/runs` accepts one exact capability
   plus the existing bounded task/context/session/run fields, selects the
   lexicographically first matching agent, and returns the existing `AgentRun`
   envelope with the selected agent identity.
4. `RunClient.route_agent(...)` and `route_agent_typed(...)` preserve raw
   compatibility and validate the selected remote run identity and JSON-safe
   envelope before returning it.
5. `AutonomousAgentRemoteAdapter.register(..., capabilities=...)` forwards
   optional bounded metadata without changing native start/resume/cancel
   behavior.
6. Public API docs, changelog, parity wording, review/QA artifacts, focused
   regressions, tracked tests, static/security gates, and clean-archive
   packaging pass.

## Constraints

- Use the Python standard library and existing `Result`, normalization, and
  authentication contracts; add no dependency.
- Capability matching is exact and case-sensitive. Selection is deterministic
  and does not imply capacity, health, fairness, or retry semantics.
- Listing returns only bounded public metadata. No handler, checkpoint,
  credentials, prompt, context, result, or error payload crosses the listing
  boundary.
- The existing named-agent routes and raw client methods remain compatible.

## Threat sketch

Assets touched: registered agent identities, public capability labels, and
remote run routing decisions. Entry points are registration metadata, the
listing route, and the capability route. The worst plausible abuse is an
unbounded or malformed label exhausting registry/response resources, or a
caller acting on a run from an unintended agent. Fixed count/byte bounds,
exact matching, deterministic identity binding, authenticated scopes, and the
existing run normalizer contain the blast radius.

## Open questions

- None for this bounded local-first contract. Distributed routing, identity
  federation, and scheduling require separate host-owned designs.

**Human confirmed:** continuation of the direct request on 2026-08-28
