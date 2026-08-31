# ADR-102: Fail-Closed Pending-Request Tool Correlation

## Status

Accepted for preview release readiness.

## Context

Durable run checkpoints retain a pending approval or human-input ID, while the
corresponding approval/input record retains the `tool_call_id` that created
it. Resume used the request record to execute or consume first and searched
the checkpoint messages afterward. If the checkpoint was corrupted or a
request was paired with the wrong run cursor, an approved handler could run or
a response could be consumed before the mismatch was detected.

## Decision

Before any pending-request state transition in both sync and async resume:

1. load the authoritative approval or human-input record;
2. verify its `tool_call_id` identifies a persisted tool-result placeholder;
3. return `RUN_PENDING_TOOL_MISSING` on mismatch;
4. only then wait, consume, replay, execute, replace the placeholder, and save
   the running checkpoint.

The existing latest-placeholder replacement behavior remains unchanged for a
valid matching ID. A failed correlation does not consume the input record,
execute an approved handler, or clear the pending checkpoint ID.

## Alternatives considered

| Alternative | Reason not selected |
|---|---|
| Execute or consume and validate during replacement | Rejected: a malformed cursor could cause an irreversible handler side effect or lose a response before failing. |
| Trust the pending request ID alone | Rejected: the ID identifies a record, not the tool placeholder in the checkpoint being resumed. |
| Add a second persisted tool-call field to every checkpoint | Rejected: the request record already owns the tool-call identity; duplicating it would create another consistency field. |
| Validate the request's tool-call identity before any transition | Selected: it closes the local side-effect/consumption window without changing the public checkpoint schema. |

## Consequences and boundaries

Corrupted or mismatched local cursors fail closed before the dangerous part of
resume, and both sync and async paths share the same correlation rule. This
does not provide globally unique IDs, distributed request delivery, remote
repair, notification guarantees, or exactly-once external effects. Hosts
remain responsible for checkpoint/request co-location and idempotent handlers.

## Evidence

Focused regressions cover sync and async approval execution plus sync and async
human-input consumption. Each proves `RUN_PENDING_TOOL_MISSING`, no handler
call or record consumption, and preserved pending state. Full repository,
static, package, and independent review evidence is recorded in the Slice 157
QA and review records.
