# ADR-012: Fail-closed approval for autonomous tools

**Status:** Accepted
**Date:** 2026-08-24

## Context

MAPLE tools can be marked `requires_approval=True`, and an autonomous agent
can also require approval by tool name. The execution boundary already rejects
missing approval callbacks, but the autonomous ReAct path previously checked
the callback only when it existed. A required tool could therefore execute
without an approval decision.

## Decision

At the moment of autonomous tool execution:

- a required tool with no approval callback returns a typed
  `APPROVAL_REQUIRED` tool result and never invokes its handler;
- a callback exception returns `APPROVAL_ERROR` and fails closed;
- a false callback result returns `APPROVAL_DENIED` and never invokes the
  handler;
- tool names and exception types are bounded metadata; arguments are not
  copied into approval errors.

The ReAct loop continues after a denied or unavailable action so the model can
observe the typed tool result and choose a safe response. Durable human pause,
approval state editing, and request-for-information events remain separate
workflow work.

## Consequences

Positive:

- The default autonomous path cannot silently bypass a declared approval
  requirement.
- Approval failures are observable as structured tool results and retain
  sibling results during async fan-out.
- No dependency or transport change is required.

Accepted limitation:

- Approval is still callback-based and in-memory; durable approval checkpoints
  are not claimed by this decision.
