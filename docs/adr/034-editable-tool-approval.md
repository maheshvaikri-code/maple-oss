# ADR-034: Persist bounded edited arguments in tool approvals

**Date:** 2026-08-26  
**Status:** accepted  
**Deciders:** Chief Architect, Backend, Security, QA

## Context

MAPLE's durable tool approval boundary previously allowed only approve or deny.
That protects side effects but forces an operator to deny and recreate a request
when a small correction to the proposed arguments is needed. The correction
must survive file-store restart and durable sync/async run resume without
weakening one-time consumption or allowing unbounded operator input.

## Decision

We will add an optional keyword-only `edited_arguments` object to approval
decisions. The value is accepted only with `approved=True`, copied through the
existing JSON compatibility, depth, item, and byte limits, persisted inside the
immutable decision record, and used by `execute_approved_tool()` after the
approval is claimed. `None` preserves the original model arguments; an empty
object is an intentional replacement. Invalid edits leave the pending record
unchanged and return `APPROVAL_DECISION_INVALID`. This slice covers one edited
tool call only; arbitrary host questions/forms, multiple interaction rounds,
cross-process leases, and exactly-once external effects remain separate
boundaries.

## Alternatives considered

| Option | Pros | Cons | Why not |
|--------|------|------|---------|
| A (chosen): optional bounded replacement in `ApprovalDecision` | Additive API; restart-safe; reuses existing quotas; preserves approve/deny and one-time consume semantics | One replacement object cannot express multi-turn forms or per-field policy | Sufficient for the current bounded tool-approval gap without claiming general HITL |
| B: mutate `ApprovalRequest.arguments` before approval | Small record shape; tool execution could reuse the existing field | Blurs model proposal and operator decision; creates a mutable approval identity and weaker audit semantics | The original proposal must remain auditable and immutable |
| C / do nothing: deny and recreate | No schema or persistence change | Operator corrections are slow and create a new request identity | Does not close the identified bounded edit gap |

## Consequences

- Positive: operators can correct bounded tool arguments without recreating a
  request; in-memory and file stores have the same persisted behavior; sync and
  async durable resume execute the recorded replacement.
- Negative / debt accepted: edits are opaque JSON objects at this layer; tool-
  specific field authorization, multi-round interaction, cross-process leases,
  and exactly-once external side effects remain host responsibilities or
  follow-on work. A consumed handler failure still requires a new approval.
- Security: invalid, non-JSON, non-finite, too-deep, too-large, and denied-with-
  edit decisions fail closed before persistence. Hosts must protect approval
  files because argument values may contain sensitive data.
- Invalidation triggers: a requirement for arbitrary request/response HITL,
  per-field operator authorization, cross-process decision races, or a durable
  audit schema that distinguishes more than one edit round would reopen this
  decision.
