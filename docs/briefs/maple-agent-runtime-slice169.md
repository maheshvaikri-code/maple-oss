# Project Brief - native autonomous-agent remote transport adapter

**Date:** 2026-08-28
**Class:** L - public runtime adapter and authenticated durable-resume boundary
**Requested by:** human

## Problem

MAPLE's authenticated `RunServer` can invoke and resume host-owned agent
handlers, but a native `AutonomousAgent` still requires hand-written callback
wrappers. That makes remote durable resume easy to wire incorrectly and leaves
provider/runtime error details exposed unless each host writes its own adapter.

## Scope

- In: `AutonomousAgentRemoteAdapter` with native start and resume bindings,
  caller-owned `AgentRunStore` binding, bounded `Goal` to `AgentRun` mapping,
  sanitized runtime failures, registration into `AgentRegistry`, tests, and
  public documentation.
- In: optional caller-supplied cooperative cancel callback remains explicit;
  the adapter does not guess how a native agent cancels an active run.
- Non-goals: new HTTP routes, remote checkpoint transfer, automatic retries,
  distributed routing/scheduling, push notifications, identity federation,
  arbitrary code execution, or exactly-once side effects.

## Acceptance criteria (numbered, testable)

1. The adapter validates a native agent and caller-owned run store, binds the
   store through the agent's public setter, and registers the agent under its
   bounded `agent_id`.
2. An authenticated remote start delegates task/context/session/run values to
   the native `pursue_goal_with_context` API and returns a normalized
   `AgentRun` with the same run identity and supported status.
3. An authenticated remote resume delegates the requested run ID to the
   native `resume_run` API and returns a normalized `AgentRun`.
4. Native failed results, exceptions, invalid goal identities, and unsupported
   statuses fail closed with bounded generic errors; provider exception text
   and private result details do not cross the adapter error boundary.
5. Existing `AgentRegistry`, `RunServer`, raw/typed `RunClient`, and local
   handler contracts remain compatible. Cancellation is registered only when
   an explicit host callback is supplied.
6. Public API documentation, changelog, parity wording, release plan, review,
   QA report, and package evidence are synchronized.
7. Focused and tracked tests plus static, security, and archive package gates
   pass.

## Constraints

- Python standard library and existing `AgentRunStore`, `AgentRegistry`,
  `AutonomousAgent`, and `Result` contracts only; no dependency changes.
- The adapter must not synthesize or mutate checkpoints. The native agent owns
  checkpoint contents and the host passes the same store to `RunServer` for
  inspection/resume routes.
- A remote cancel callback is caller-owned because the native agent has no
  universal force-free cancellation operation.

## Threat sketch

Assets touched: native agent credentials/provider state, durable run identity,
checkpoint store, task/context payload, and remote result/error data. Untrusted
inputs are authenticated route payloads, run IDs, native callback output, and
provider exceptions. Worst plausible abuse is a malformed native result being
treated as another run, a private provider exception crossing HTTP, or an
adapter silently claiming a checkpoint it did not persist. Identity checks,
bounded existing normalization, generic error mapping, and caller-owned store
binding contain the blast radius.

## Open questions

- None. Remote cancellation semantics are intentionally explicit rather than
  inferred from a native agent API that does not own a run-wide cancel registry.

**Human confirmed:** continuation of the direct request on 2026-08-28
