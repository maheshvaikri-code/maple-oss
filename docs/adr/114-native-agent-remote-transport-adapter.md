# ADR-114: Native Autonomous-Agent Remote Transport Adapter

**Date:** 2026-08-28
**Status:** accepted
**Deciders:** Chief Architect, Backend Engineer, Interop, Security Reviewer

## Context

The authenticated `AgentRegistry`/`RunServer` contract already supports
bounded agent invocation and explicit resume callbacks. A host that wants to
expose a native `AutonomousAgent` must currently write both callbacks, map its
`Goal` result to `AgentRun`, bind the same durable store to the agent and
server, and decide how to redact failures. Repeated wrappers create a
cross-host compatibility and security risk.

## Decision

Add `AutonomousAgentRemoteAdapter` in a separate adapter module. It accepts a
native agent-like object and a caller-owned `AgentRunStore`, binds the store
through `set_run_store`, and registers bounded start and resume callbacks with
`AgentRegistry`. It maps only `completed` and `paused` goals to successful
`AgentRun` data; failed and cancelled goals become terminal runs with generic
errors. Callback `Result.err` values and exceptions become one generic
`AGENT_RUNTIME_ERROR` without copying provider details. An explicit
caller-supplied cancel callback may be passed to registration; no cancellation
behavior is inferred.

## Data flow and failure modes

```text
host-owned AutonomousAgent + AgentRunStore
  -> adapter validates and binds the store
  -> AgentRegistry start/resume callback
  -> native pursue_goal_with_context/resume_run
  -> Goal identity/status mapping
  -> existing AgentRegistry/RunServer AgentRun normalization
  -> authenticated RunClient typed or raw response
```

- A missing adapter method, invalid agent ID, or invalid store fails at
  construction/registration before serving requests.
- A native callback exception or error is converted to bounded generic
  `AGENT_RUNTIME_ERROR`; the original error is not returned over HTTP.
- A mismatched run ID or unsupported goal status returns
  `AGENT_RUNTIME_RESULT_INVALID` and no `AgentRun` is emitted.
- The adapter does not save checkpoints itself. The native agent's store is
  the source of truth, and the host must pass that same store to `RunServer`.

## Alternatives considered

| Option | Pros | Cons | Why not |
|---|---|---|---|
| Dedicated adapter with explicit store binding (chosen) | Reusable, typed, redacts failures, preserves current transport | Native agent still owns checkpoint details and cancellation policy | Closes the repeated-wrapper gap without changing the wire contract |
| Add native-agent knowledge to `RunServer` | One configuration point | Couples HTTP server to the full autonomous runtime and creates import cycles | Violates the existing host-owned handler boundary |
| Keep host-written callbacks | No library change | Repeated mapping, store wiring, and error-redaction mistakes | Does not make remote durable resume a reliable public path |
| Serialize and transfer checkpoints over HTTP | Cross-host restore potential | Sensitive state transfer, schema/version, auth, and exactly-once complexity | Requires a separate distributed restore protocol |

## Consequences

- Positive: one documented path exposes a native durable agent through
  authenticated remote invocation and resume while retaining local ownership of
  checkpoint data.
- Negative / debt accepted: native agent execution remains synchronous at the
  `AgentRegistry` boundary, and cancellation requires an explicit host
  callback. Remote routing, scheduling, push, identity federation, and
  exactly-once effects remain separate.
- Invalidation triggers: a requirement for cross-host checkpoint movement,
  automatic remote cancellation, or distributed routing reopens this ADR.
