# ADR-044: Bounded handoff context filtering

- Status: Accepted
- Date: 2026-08-26
- Owners: Chief Architect / Backend / Security / QA

## Context

MAPLE's handoff tool already delegated a bounded task with approval by default,
but it had no explicit context boundary. Passing the caller's working state
implicitly would blur agent ownership and could disclose unrelated data to a
specialist. Framework parity requires context-aware delegation, while local
handoffs must remain deterministic and fail closed.

## Decision

Extend `create_handoff_tool` with an optional `allowed_context_keys` allowlist
and an optional bounded JSON `context` argument. Context is recursively copied
before delegation with limits on keys, items, depth, string length, and total
UTF-8 bytes. Keys outside the factory allowlist return
`HANDOFF_CONTEXT_KEY_DENIED` before the target is called.

Non-empty context requires the target to explicitly expose
`pursue_goal_with_context(task, context)`. A target without that method returns
`HANDOFF_CONTEXT_UNSUPPORTED`; calls without context preserve the legacy
`pursue_goal(task)` path. `AutonomousAgent` implements the context-aware method
and places the copied context in a system message marked as data, not
instructions. Because that initial message is part of the existing run
checkpoint, local durable resume retains the context.

## Consequences

- Handoff callers declare which context keys may cross the ownership boundary.
- Target agents receive a detached bounded copy and cannot mutate caller state
  through the handoff object.
- Legacy targets and one-argument handoff calls remain compatible.
- Context filtering is local policy, not authentication, authorization, secret
  redaction, or proof that a model will obey the data-only instruction.
- Async target invocation, durable handoff IDs/leases, explicit ownership
  transfer, remote routing, and exactly-once external effects remain separate
  contracts.

## Rejected alternatives

- **Pass the full caller state:** leaks unrelated state and creates an
  unbounded prompt/checkpoint surface.
- **Silently drop unknown keys:** hides a policy mistake from the caller and
  makes the target's context ambiguous.
- **Infer context support from a callable signature:** makes ownership and
  compatibility dependent on reflection heuristics rather than an explicit
  target contract.
