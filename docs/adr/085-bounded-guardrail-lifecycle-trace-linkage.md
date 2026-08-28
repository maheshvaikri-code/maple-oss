# ADR-085: Bounded guardrail lifecycle and trace linkage

Status: Accepted for preview

Date: 2026-08-27

## Context

MAPLE already applies input and output guardrails synchronously and fails closed
on rejection, exceptions, malformed callbacks, and malformed results. The
decision was not uniformly observable, however: hosts could see the final
error but not the ordered lifecycle of each guardrail or its relationship to a
local agent run/model span.

## Decision

Add the bounded `GuardrailEvent` and `GuardrailObserver` contracts. The
optional observer on `run_guardrails(...)` receives `started`, `passed`,
`rejected`, or `failed` transitions with only stage, index, status, and
optional trace/span IDs. Observer exceptions are isolated and cannot change the
policy decision.

When an `AutonomousAgent` has an event stream, input and output guardrail
transitions are published as `guardrail.*` lifecycle events. The agent supplies
the run/goal trace identity and active model span identity where available.
Guarded values, prompts, result payloads, and callback error text never enter
the event.

## Alternatives considered

| Alternative | Decision |
| --- | --- |
| Expose only the final guardrail error | Rejected: it hides ordering and successful policy decisions needed for local operations. |
| Copy the guarded value or rejection payload into events | Rejected: it widens the policy observability boundary and can leak sensitive data. |
| Let observer failures fail the run | Rejected: telemetry must not weaken fail-closed enforcement. |
| Add remote policy delivery or distributed enforcement | Rejected: identity, tenancy, transport, and consistency require a separate host-owned contract. |

## Security and failure boundaries

- Lifecycle metadata is bounded and contains no guarded input/output or raw
  callback error text.
- Guardrail execution remains synchronous, ordered, and fail closed. This ADR
  does not add retries, bypasses, or policy weakening.
- Event-stream publication remains best-effort under the existing bounded
  stream contract; a dropped lifecycle event does not change the run result.
- Remote policy engines, principal scopes, hosted tracing, sandboxing, and
  exactly-once external effects remain outside this contract.

## Invalidation triggers

Reopen this decision if guardrails require async callback execution, remote
policy evaluation, durable policy decisions, principal-scoped enforcement, or
mandatory audit delivery.
