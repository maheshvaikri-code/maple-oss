# ADR-115: Bounded Agent Capability Discovery and Routing

**Date:** 2026-08-28
**Status:** accepted
**Deciders:** Chief Architect, Backend Engineer, Interop, Security Reviewer

## Context

`AgentRegistry` currently maps one caller-supplied agent ID to one host-owned
handler. The authenticated transport exposes that exact-ID operation, but a
remote caller has no bounded way to discover public capabilities or request a
capability without encoding host routing policy in application code. Native
agents bound through `AutonomousAgentRemoteAdapter` likewise cannot advertise
capabilities.

## Decision

Add an immutable `AgentDescriptor` containing only an agent ID and a bounded,
unique tuple of capability labels. Extend registration with an optional
`capabilities` argument, defaulting to no capabilities for compatibility.
`AgentRegistry.list_agents()` returns descriptors sorted by agent ID. A new
exact-match `AgentRegistry.route(...)` resolves the lexicographically first
registered agent with the requested capability and delegates to the existing
validated `run(...)` path.

Expose the metadata through authenticated `GET /v1/agents` using the existing
`agent:read` scope. Expose capability invocation through authenticated
`POST /v1/agent-routes/runs` using `agent:invoke`. Add raw and typed
`RunClient.list_agents()`, `route_agent()`, and `route_agent_typed()` methods;
the typed route validates the selected run envelope while allowing the server
to choose its agent identity. Extend `AutonomousAgentRemoteAdapter.register`
with the same optional capability metadata.

The route is deterministic selection, not a scheduler. It performs no
failover, retry, load balancing, health check, queue admission, checkpoint
transfer, identity federation, push delivery, or exactly-once side effect.

## Data flow and failure modes

```text
remote caller
  -> bearer authentication + agent scope
  -> bounded capability/task/context parsing
  -> exact registry capability match
  -> deterministic agent ID selection
  -> existing handler/native-agent invocation
  -> existing AgentRun identity + JSON normalization
  -> bounded response envelope
```

- Invalid capability, task, context, or registration metadata is a caller
  error and causes no handler invocation.
- No matching capability returns `AGENT_ROUTE_NOT_FOUND`; no fallback or retry
  occurs.
- A malformed handler result follows the existing `AGENT_RESULT_INVALID`
  boundary and is never returned as a typed run.
- Listing without a configured registry returns the existing unavailable
  response and never exposes partial registry state.
- Capability labels are metadata only; authorization remains controlled by the
  existing bearer token and principal scope policy.

## Alternatives considered

| Option | Pros | Cons | Why not |
|---|---|---|---|
| Add bounded descriptors and deterministic exact-match routing (chosen) | Small additive surface; supports native and host handlers; reuses existing validation and run envelope | Does not balance load or recover from failures | Correct local-first parity increment without pretending to be a distributed scheduler |
| Require callers to keep an agent-ID route table | No server change | Duplicates host policy, prevents discovery, and becomes stale | Does not solve remote composition |
| Add health-aware weighted routing and failover | Better fleet utilization | Requires health, leases, retries, idempotency, and scheduling contracts | Too much distributed policy for this boundary |
| Add remote service discovery or identity federation | Fleet-wide discovery | Requires network trust, issuer/audience rules, tenancy, and credential lifecycle | Must be a separately approved host-owned security design |

## Consequences

- Positive: remote callers can inspect public capabilities and compose named
  or capability-routed agents with deterministic behavior; native adapters can
  participate without handwritten registration glue.
- Negative / debt accepted: selection is lexicographic and can repeatedly
  choose one agent; no health, capacity, fairness, or distributed ownership is
  claimed. The listing is metadata-only and not a checkpoint inventory.
- Invalidation triggers: a requirement for load balancing, failover,
  distributed leases, remote identity federation, durable queueing, or
  exactly-once effects reopens this decision with a separate architecture.
