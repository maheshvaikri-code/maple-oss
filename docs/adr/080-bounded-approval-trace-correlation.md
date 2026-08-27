# ADR-080: Bounded Approval Trace Correlation

Status: Accepted for preview

Date: 2026-08-27

## Context

MAPLE can persist an approval request, pause a run, and later execute or replay
the approved tool outcome. Local `TraceSpan` and lifecycle event records already
identify the model step, but the durable approval envelope did not retain that
same correlation context. Operators could inspect an approval but could not
reliably join it to the model/tool span that created the request after a
restart.

## Decision

Add optional bounded `trace_id` and `span_id` fields to `ApprovalRequest`.
They are validated as non-empty strings without control characters and are
persisted by both in-memory and file approval stores. Existing records without
the fields remain valid. When an approval request is created from an autonomous
tool call under a local model span, the agent copies the span identifiers into
the request.

Pending approval tool errors include the same correlation fields. Normal sync
and async `tool.completed` lifecycle events now retain the active model
`trace_id`/`span_id` and the pending `approval_id` when one is present. This
creates a bounded join across request, pause, and local trace records without
copying prompts, tool arguments, tool results, or provider objects.

The fields are observational. They do not alter approval decisions, consume
semantics, replay behavior, notification delivery, authentication, or external
side-effect guarantees. Hosted trace storage, principal identity, remote trace
search, and cross-process trace correlation remain host-owned or deferred.

## Alternatives considered

| Alternative | Decision |
| --- | --- |
| Persist the full prompt/conversation with each approval | Rejected: it expands sensitive-data retention and is unnecessary for a trace join. |
| Use approval IDs as trace IDs | Rejected: an approval identity and a trace identity have different ownership and lifecycle. |
| Add a hosted tracing dependency | Deferred: the local store/event contracts must remain dependency-free. |
| Leave approvals uncorrelated | Rejected: durable pause/replay inspection loses useful local audit context. |

## Security and failure boundaries

- Correlation values are bounded and control-character-free; arbitrary payloads
  are not copied into approval or span records.
- Existing approval argument and execution-result limits remain unchanged.
- Older file records hydrate with `None` correlation fields for compatibility.
- Correlation is best-effort observability. Missing spans, sampling, record
  eviction, file restart, and hosted transport do not block the approval path.
