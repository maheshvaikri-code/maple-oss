# ADR-084: Bounded manager-style agent-as-tool delegation

Status: Accepted for preview

Date: 2026-08-27

## Context

The runtime already exposes handoffs, where a caller can transfer bounded
ownership to a specialist and optionally persist that transfer. The comparison
frameworks also expose the distinct manager-style pattern in which one agent
invokes another as a tool and keeps orchestration ownership. MAPLE needed that
surface without implying remote routing, scheduling, or durable ownership.

## Decision

Add `create_agent_tool(...)` as a local, dependency-free factory for a normal
MAPLE `Tool`. It invokes a target agent's `pursue_goal` method, or its declared
`pursue_goal_async` method through `Tool.execute_async`. Non-empty context is
copied through the existing bounded JSON boundary and requires an explicit
`allowed_context_keys` allowlist plus the corresponding context-aware target
method.

The result is reduced to the target agent ID, goal ID, status, and result.
Target error payloads, prompts, traces, and provider details do not cross the
tool boundary. Approval is required by default because the nested agent may
invoke tools or create side effects. The factory does not create a handoff
record, transfer ownership, retry the target, or execute remote work.

## Alternatives considered

| Alternative | Decision |
| --- | --- |
| Reuse `create_handoff_tool` directly | Rejected: it would conflate manager delegation with ownership transfer and expose handoff semantics in the public API. |
| Add a remote agent router | Rejected: authentication, scheduling, tenancy, delivery, and cancellation require a separate host-owned contract. |
| Let the nested agent receive unrestricted context or raw errors | Rejected: it would widen the trust boundary and leak child/provider details. |
| Add a new dependency or agent protocol | Rejected: the local callable contract is sufficient and keeps the preview dependency-free. |

## Security and failure boundaries

- The task and optional context use the existing bounded tool/schema and JSON
  copy limits; context keys outside the explicit allowlist fail before target
  invocation.
- A legacy target receiving non-empty context fails closed because the target
  has not declared a context-aware contract.
- Target exceptions, malformed results, and child error payloads are mapped to
  stable typed errors without forwarding private messages or traces.
- Approval remains enabled by default. No sandbox, network, remote identity,
  scheduler, retry, durable child-run replay, or exactly-once side-effect
  guarantee is introduced.

## Invalidation triggers

Reopen this decision if manager-style delegation needs remote routing,
principal scopes, durable child-run coordination, cancellation propagation,
automatic retries, or exactly-once side effects.
