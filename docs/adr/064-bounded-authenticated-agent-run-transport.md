# ADR-064: Bounded Authenticated Agent-Run Transport

- Status: Accepted
- Date: 2026-08-26
- Decision owners: Chief Architect, Backend, Security, QA

## Context

MAPLE has local agent handoff and durable ownership records, but those
capabilities do not cross a process boundary. The existing dependency-free
`RunServer`/`RunClient` contract provides bounded authenticated workflow
transport and is a suitable seam for a host that needs to invoke a named
agent. The seam must not silently become a scheduler, a durable remote
handoff protocol, or an exactly-once side-effect mechanism.

## Decision

Add an optional host-owned `AgentRegistry` to `RunServer` and a matching
`RunClient.run_agent(...)` operation:

- `AgentRegistry.register(agent_id, handler)` binds a bounded identifier to a
  synchronous callback. The callback receives `task`, copied JSON `context`,
  optional `session_id`, and a request `run_id`.
- `POST /v1/agents/<agent_id>/runs` accepts a non-empty task, optional session
  and run identifiers, and a bounded JSON context. Missing run IDs receive a
  generated correlation ID; supplied IDs are passed through unchanged.
- The callback returns `Result[AgentRun, Error]`. A successful response is a
  JSON-safe `{agent_id, run_id, status, result, error}` envelope where status
  is `completed`, `paused`, or `failed`. The registry rejects identity
  mismatches, unsupported statuses, malformed errors, non-JSON values, and
  oversized results.
- Attaching an `AgentRegistry` requires `RunServer(auth_token=...)`. The
  existing loopback-only bind, constant-time bearer check, request/path/
  response bounds, and no-retry client behavior remain in force.
- A handler exception is converted to a generic typed error; exception text
  is not sent over the transport. The handler owns agent construction,
  provider selection, persistence, and any async adaptation.

## Bounds and failure semantics

Agent IDs, session IDs, and run IDs are limited to 256 UTF-8 bytes; task text
is limited to 8 KiB; context is limited to 32 top-level keys, 128 items per
object/array, depth 8, 8,192-character strings, and 32 KiB serialized UTF-8.
The standard server request/response limits remain the outer boundary.

The transport performs one synchronous invocation and no automatic retry.
There is no remote result store, duplicate suppression, lease, cancellation
route, resume route, or delivery guarantee. A timeout or lost response leaves
the handler's side effects host-defined. Callers must supply their own
idempotency policy before retrying a request.

## Alternatives considered

| Option | Pros | Cons | Decision |
|---|---|---|---|
| Add a bounded authenticated agent-run route to the existing transport | Reuses tested bounds/auth/client behavior and gives hosts one small cross-process seam | Does not solve remote durability, scheduling, or exactly-once effects | Chosen |
| Extend local handoff stores into a remote protocol | Could preserve ownership transitions across processes | Requires leases, fencing, replay, authentication scopes, retries, and conflict semantics before a safe contract exists | Deferred |
| Add a broker-specific remote adapter | Can use existing NATS/S2/Redis/RabbitMQ integrations | Couples the public agent API to optional infrastructure and introduces delivery semantics the runtime cannot guarantee | Rejected for this slice |

## Consequences

Hosts can expose a named agent through the same dependency-free authenticated
transport as workflows and can adapt `AutonomousAgent.pursue_goal` into the
typed `AgentRun` envelope. The local runtime remains safe to package without
new dependencies. Remote handoff ownership, hosted scheduling, TLS
termination/token issuance, tenancy/scopes, streaming events, cancellation,
durable resume, and exactly-once external effects remain separate reviewed
boundaries.

## Reopening triggers

Reopen this ADR before adding retries, remote ownership transitions, result
inspection, cancellation, or resume. Each requires an explicit state machine,
authentication/authorization scope, persistence and fencing model, and
failure-path test matrix.
