# ADR-107: Opt-in local replay for agent-as-tool results

**Date:** 2026-08-28
**Status:** accepted
**Deciders:** Chief Architect

## Context

MAPLE already has an `ExecutionJournal` that stores bounded successful tool
results keyed to a parent agent run, step, tool position, and input digest.
`create_agent_tool` is a normal `Tool`, but its factory did not expose the
existing `replay_policy` option. A parent checkpoint failure after a successful
local child call could therefore repeat that child call during recovery.

## Decision

Add `replay_policy` to `create_agent_tool`, defaulting to
`TOOL_REPLAY_DISABLED`, and pass it unchanged to the returned `Tool`. Callers
may opt into `TOOL_REPLAY_REUSE_SUCCESS` when the parent has an
`ExecutionJournal`, supplies a durable run cursor, and accepts the explicit
non-approval boundary. The existing parent agent replay implementation owns
input hashing, bounded serialization, conflict detection, and tool-call-ID
rebinding.

Only successful serialized results are replayed. Failed, cancelled, malformed,
or journal-less calls execute through the existing path. Approval-required
agent tools remain excluded by the parent replay guard so approval records and
their terminal outcomes retain ownership of that recovery contract.

## Consequences

- Local manager-style delegation can avoid repeating a successful child call
  after a parent checkpoint crash window.
- The feature is additive and keeps replay disabled unless explicitly chosen.
- A journal save failure after child execution still reports the existing
  persistence error; external effects remain at-least-once.
- This does not create a child-run store, restore child state, coordinate
  remote work, roll back effects, or provide exactly-once semantics.

## Alternatives considered

| Option | Pros | Cons | Why not |
|---|---|---|---|
| Reuse the existing parent journal through an opt-in factory policy (chosen) | Small additive surface; inherits bounded, tested replay behavior | Requires a parent journal and non-approval tool | Fits the existing local execution contract |
| Always replay agent tools | Transparent recovery | Could suppress intentional child reruns and surprise callers | Changes current semantics and side-effect expectations |
| Add a new child-run store and resume protocol | Richer lifecycle recovery | New identity, ownership, payload, and crash semantics | Needs a separate reviewed lifecycle design |
| Derive a replay key from task text alone | Easy to call | Collides across runs and cursor positions | Violates the parent journal’s identity boundary |

**Invalidation triggers:** a reviewed delegated child-run lifecycle protocol,
an approval-compatible replay contract, or a distributed result-coordination
boundary would reopen this decision.
