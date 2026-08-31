# ADR-113: Typed Remote Agent-Run Lifecycle Results

**Date:** 2026-08-28
**Status:** accepted
**Deciders:** Chief Architect, Backend Engineer, Interop, Security Reviewer

## Context

`RunClient` already exposes authenticated remote agent invocation, resume, and
cooperative cancellation. Those methods intentionally preserve a generic
dictionary response for wire compatibility. Public callers that need a typed
run must parse the envelope themselves, and the remote handoff adapter has
duplicated that parsing and validation.

## Decision

Add additive `RunClient.run_agent_typed(...)`,
`RunClient.resume_agent_run_typed(...)`, and
`RunClient.cancel_agent_run_typed(...)` methods. They call the existing raw
methods, validate the `{"run": ...}` envelope, enforce the requested agent/run
identity, reuse the existing `AgentRun` normalization, and return `Result[AgentRun,
Error]`. The typed cancel method additionally requires a `cancelled` status.
Existing raw methods remain unchanged. The new methods do not add retries,
storage, routes, push delivery, or distributed side-effect guarantees.

## Data flow and failure modes

```text
caller
  -> existing authenticated raw client method
  -> bounded response envelope validation
  -> agent/run identity validation
  -> existing AgentRun normalization and JSON bounds
  -> typed AgentRun or generic typed error
```

- Transport errors remain the existing typed client errors.
- Missing or malformed run envelopes return `AGENT_RESPONSE_INVALID` without
  returning remote raw payloads.
- A remote run error remains data on a valid `AgentRun`; callers decide whether
  the lifecycle is successful. A cancel response with any status other than
  `cancelled` fails closed.
- Existing raw methods and the `RemoteHandoffTarget` boundary retain their
  current behavior.

## Alternatives considered

| Option | Pros | Cons | Why not |
|---|---|---|---|
| Add typed methods over existing transport (chosen) | Additive, small, reuses validation and preserves wire compatibility | Two method families remain during migration | Lowest-risk developer-facing improvement |
| Change existing methods to return `AgentRun` | One API surface | Breaks callers relying on response mappings and nested envelope shape | Public compatibility cost is not justified |
| Add a new remote lifecycle HTTP route | Could return a richer native object | Duplicates routing/auth and changes host contract | No transport capability is missing |
| Leave callers to parse dictionaries | No code change | Duplicated validation and inconsistent failure handling | Does not provide a reliable typed public contract |

## Consequences

- Positive: remote lifecycle callers can consume the same validated `AgentRun`
  type as local host handlers, and handoff code can migrate to one parser later.
- Negative / debt accepted: inspect/history retain metadata-oriented dictionary
  responses, and remote durable restore remains dependent on host callbacks.
- Invalidation triggers: a requirement for remote checkpoint transfer,
  distributed routing, or retry/idempotency semantics reopens the transport
  design separately.
