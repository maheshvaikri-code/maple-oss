# ADR-035: Add a bounded durable human-input request/response boundary

**Date:** 2026-08-26  
**Status:** accepted  
**Deciders:** Chief Architect, Backend, Security, QA

## Context

MAPLE's durable approval records can now approve, deny, or edit one tool call,
but they cannot represent a question or form whose answer should become a
normal tool result. The workflow runtime already has a generic pause value, yet
durable ReAct runs need a persisted request identity, response validation, and a
resume cursor that survives process restart.

## Decision

We will add bounded in-memory and atomic file `HumanInputStore` implementations
with `HumanInputRequest` and `HumanInputDecision` records. A reserved
`request_human_input` model tool creates an idempotent request only inside a
durable agent run; its prompt and response schema are persisted, and the host
uses `respond_human_input()` or `reject_human_input()` to complete it. Responses
are JSON-safe and validated against MAPLE's bounded JSON-Schema subset before
mutation. The run checkpoint stores `pending_input_id`; sync and async resume
replace the pending tool result with the accepted response or a typed rejection
error. Consumed records retain their decision so a crash between consumption
and checkpoint save can reconstruct the tool result. Cross-process leases,
notifications, and multiple conversational rounds remain separate boundaries.

## Alternatives considered

| Option | Pros | Cons | Why not |
|--------|------|------|---------|
| A (chosen): reserved model tool plus durable request store | Gives the model a normal tool contract; persists prompt/schema/decision; integrates directly with sync/async run cursors | One request has one response; host notifications and distributed leases remain external | Closes the concrete request/response gap without claiming a general conversation engine |
| B: expose only `WorkflowPause.resume_value` | Reuses an existing pause primitive and has a small API | No shared request identity, schema/response store, or durable ReAct integration | Does not unify workflow-style interaction with agent runs |
| C: reuse `ApprovalRequest.edited_arguments` | No new module or checkpoint field | Conflates authorization with data collection and cannot represent rejection or response schemas cleanly | Approval and input have different audit and state semantics |

## Consequences

- Positive: durable sync/async ReAct runs can ask a bounded human question,
  survive restart, validate the answer, and continue with the answer as tool
  context; host rejection is explicit and typed.
- Negative / debt accepted: the tool requires a durable `run_id`; there is one
  response round per request; request listing is bounded but notification,
  authentication, cross-process leases, and retention are host responsibilities.
  A response is data, not proof that an external side effect is exactly once.
- Security: prompts, schemas, responses, and rejection reasons are bounded;
  non-JSON/non-finite/deep/oversized values and schema-invalid responses fail
  closed before persistence. Hosts must protect the input directory because
  requests may contain sensitive questions or answers.
- Invalidation triggers: a need for concurrent workers to claim one request,
  multi-round forms, field-level authorization, remote notification delivery,
  or a stronger distributed consistency contract would reopen this decision.
