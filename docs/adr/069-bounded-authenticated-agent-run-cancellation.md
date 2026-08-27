# ADR-069: Bounded Authenticated Agent-Run Cancellation

## Status

Accepted — preview capability, local-first.

## Context

MAPLE's authenticated agent-run transport can invoke host-owned handlers and
inspect or resume durable runs, but it has no remote cancellation operation.
The runtime already has cooperative cancellation primitives, while arbitrary
model providers and tool handlers cannot be force-killed safely by a library.

The next useful boundary is therefore an explicit host callback. The host
owns the cancellation token, worker lifecycle, checkpoint mutation, and
side-effect policy for the run.

## Decision

Add an optional cooperative cancellation seam:

- `AgentRegistry.register(..., cancel_handler=...)` accepts a host-owned
  callback receiving a validated `run_id`.
- `AgentRegistry.cancel(agent_id, run_id)` invokes that callback and requires
  a normalized `AgentRun` envelope whose status is `cancelled`.
- `RunServer` exposes `POST
  /v1/agents/<agent_id>/runs/<run_id>/cancel` when a cancel callback is
  registered.
- `RunClient.cancel_agent_run(...)` provides the dependency-free client
  surface.

The operation is authenticated whenever an agent registry is configured.
Callback exceptions and malformed results fail closed. The callback may
signal a `CancellationToken`, update a durable checkpoint, or coordinate a
host worker, but those policies remain outside MAPLE's transport.

## Alternatives considered

1. **Force-stop the handler thread or provider call.** Rejected because
   Python cannot safely terminate arbitrary code and forced termination can
   leave external side effects half-completed.
2. **Have the server mutate every run store automatically.** Rejected because
   the transport cannot know the host's active worker, checkpoint ownership,
   or whether cancellation is safe at the current side-effect boundary.
3. **Accept a generic cancellation flag in every handler.** Rejected for this
   slice because it would break existing host callbacks and still would not
   define how the handler observes or persists the request.

## Bounds and failure modes

- Existing path, ID, request, response, and authentication bounds apply.
- A missing cancel callback returns `501`; callback exceptions are redacted.
- A callback must return the same JSON-safe `AgentRun` envelope as invocation
  and its status must be `cancelled`; other statuses fail closed.
- No transport retry, hard thread termination, scheduler, principal scope,
  idempotency guarantee, or exactly-once external-effect claim is provided.
- The operation is cooperative: a host that does not propagate its
  cancellation signal may continue running after the response.

## Consequences

Remote operators now have a typed, authenticated cancellation request that
can be connected to the host's existing cooperative cancellation machinery.
The contract is honest about its boundary: the host remains responsible for
propagation, durable state, cleanup, and side-effect reconciliation.

