# ADR-101: Fail-Closed Pending-Request Checkpoints

## Status

Accepted for preview release readiness.

## Context

Durable agent runs use a checkpoint status and optional approval or human-input
record ID to decide how resume should reconstruct the next tool result. The
parser validated each field independently, but could accept contradictory
combinations: a paused checkpoint without a request, a running or terminal
checkpoint with a request, or both request types at once. Such a cursor does
not identify one deterministic recovery path.

## Decision

Validate the pending-request relationship during `AgentRunCheckpoint.from_dict`
normalization, which is the existing boundary used before memory and file
store writes and after loads:

- `paused` requires exactly one of `pending_approval_id` or
  `pending_input_id`;
- `running`, `completed`, and `failed` require neither pending ID;
- both pending IDs are always rejected.

Invalid combinations raise the existing parser `ValueError`; store callers
return the existing typed `RUN_CHECKPOINT_INVALID` error and leave their
current record unchanged. Direct dataclass construction remains compatible;
the persistence boundary is authoritative.

## Alternatives considered

| Alternative | Reason not selected |
|---|---|
| Infer which request to resume from the messages | Rejected: messages do not establish authoritative request ownership or type. |
| Prefer approval when both IDs are present | Rejected: silent precedence can resume the wrong side effect or lose a human-input request. |
| Validate only in `resume_run()` | Rejected: malformed state would remain loadable and could be exposed or mutated before resume. |
| Validate during checkpoint normalization | Selected: one existing memory/file persistence boundary protects writes and reloads without adding a dependency. |

## Consequences and boundaries

This makes local durable run state structurally unambiguous and preserves
existing sync/async resume behavior for valid checkpoints. It does not bind a
request ID to a globally unique tool call, deliver notifications, recover a
distributed queue, or establish exactly-once external effects. Approval and
human-input records, side-effect idempotency, and remote coordination remain
host responsibilities.

## Evidence

Focused run and lease regressions cover every invalid status/request
combination, both valid paused request types, and rejection before an existing
store record is mutated. Full repository, static, package, and independent
review evidence is recorded in the Slice 156 QA and review records.
