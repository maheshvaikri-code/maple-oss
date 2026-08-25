# ADR-019: Session-aware agent turns

**Date:** 2026-08-24  · **Status:** accepted  · **Deciders:** Chief Architect

## Context

MAPLE now has a bounded `SessionStore`, but `AutonomousAgent` still builds
each ReAct context from only the current goal and working memory. Without an
explicit binding, hosts must duplicate prompt-history assembly and can
accidentally replay stored system or tool messages as trusted instructions.

## Decision

We will add an opt-in session binding to `AutonomousAgent.pursue_goal` and
`pursue_goal_async` through `session_id` plus `set_session_store`.

- Before model execution, MAPLE loads or creates the session and appends the
  current goal as a `user` message using the loaded version as the expected
  version. A failure stops the turn before the LLM is called.
- The model context replays only stored `user` and `assistant` messages. Stored
  `system` and `tool` messages remain data in the store and are never promoted
  into the agent prompt by this binding.
- After the ReAct result, MAPLE appends one bounded `assistant` turn message.
  If that persistence step fails after execution, the returned `Goal` keeps
  the execution outcome and exposes `session_error`; the error is not hidden.
- Async session store operations run in the event loop's executor. The
  existing agent behavior remains unchanged when no session ID is supplied.

## Alternatives considered

| Option | Pros | Cons | Why not |
|---|---|---|---|
| Opt-in agent binding (chosen) | One documented path; preserves existing callers; fail-closed pre-call state | A concurrent writer can cause a session conflict; post-call persistence cannot undo model/tool effects | Makes the side-effect boundary explicit and keeps session use optional |
| Automatically bind every agent to a hidden session | Convenient for demos | Changes prompt behavior and persistence for existing callers; unclear retention/security | Backward compatibility and data ownership require explicit host choice |
| Require hosts to assemble history manually | Small agent diff | Duplicates conversion, role filtering, CAS, and failure handling across hosts | Recreates the interoperability bug this slice is meant to remove |

## Consequences

- Positive: a caller can opt into restartable, bounded multi-turn context with
  one store and one agent API for sync or async turns.
- Negative / debt accepted: full ReAct trace persistence, tool-result replay,
  summarization/token-window compaction, authentication/tenant ownership, and
  replay-safe execution remain separate capabilities.
- Invalidation triggers: reopen when sessions need multi-agent ownership,
  durable trace replay, automatic compaction, or cross-process turn leases.
