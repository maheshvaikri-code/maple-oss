# ADR-062: Bounded Agent Tool-Result Replay

- Status: Accepted
- Date: 2026-08-26
- Decision owners: Chief Architect, Backend, Security, QA

## Context

Durable agent runs checkpoint the conversation after a completed ReAct step.
If a tool has already produced an external effect and the process fails before
that checkpoint is committed, a resumed run can ask the model for the same
tool call and invoke the handler again. MAPLE already has a bounded execution
journal for workflow outputs, but no equivalent contract for agent tools.

## Decision

Reuse the existing `ExecutionJournal` contract for explicitly opted-in
successful tool results:

- `Tool(replay_policy="reuse_success")` enables the behavior; the default
  `"disabled"` preserves existing execution semantics.
- `AutonomousAgent.set_execution_journal()` attaches an in-memory or atomic
  file-backed journal.
- The deterministic invocation identity hashes the agent, run, reasoning
  step, bounded tool-call ordinal, tool name, and authorized JSON arguments.
  The provider's tool-call ID is intentionally not part of the identity so a
  regenerated provider ID can reuse the result.
- Only successful `ToolResult` values are recorded. Approval-required tools
  are excluded because approval stores have their own one-time ownership
  contract; human-input handling is also excluded.
- A matching journal record returns a result with the current provider call
  ID without running the handler. Journal read or write failures return typed
  tool errors; a write failure explicitly warns that the external effect may
  already have occurred.
- The journal remains bounded by the existing record and run quotas and must
  be retained/cleared by the host. This closes a saved-record crash window; it
  does not provide exactly-once effects, distributed locking, or transactional
  coordination with external systems.

## Alternatives considered

| Option | Pros | Cons | Why not |
|---|---|---|---|
| Opt-in result replay through `ExecutionJournal` (chosen) | Reuses tested bounded storage, supports sync/async agents, and makes the side-effect boundary explicit | A crash before journal save can still repeat an effect; approvals remain separate | Best local-first increment without claiming exactly-once behavior |
| Cache every tool result automatically | Fewer configuration steps | Unsafe for reads, time-sensitive calls, and side effects; changes existing behavior | Violates fail-closed compatibility and side-effect ownership |
| Add a distributed exactly-once coordinator | Stronger fleet semantics in theory | Requires transactional external systems, identity, leases, deployment, and provider-specific contracts | Hosted/distributed scope is not approved and cannot be inferred from a local journal |
| Store handler objects or executable closures in checkpoints | Could resume an in-flight handler | Unsafe serialization, non-portable process state, and code execution risk | Checkpoints remain data-only by policy |

## Consequences

- Positive: explicitly idempotent or otherwise replay-safe tools can avoid a
  duplicate local handler call after a saved journal record, including when the
  regenerated provider call ID differs.
- Negative / debt accepted: journal persistence happens after the handler, so
  the unsaved crash window remains at-least-once. Approval-resume replay and
  remote aggregation remain separate boundaries.
- Invalidation triggers: a requirement for exactly-once external effects,
  cross-host ownership, or automatic approval-result replay reopens this ADR
  before implementation.
