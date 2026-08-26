# ADR-041: Bounded multi-round human input

- Status: Accepted
- Date: 2026-08-26
- Owners: Chief Architect / Backend / Security / QA

## Context

MAPLE already persisted one-shot human-input requests, decisions, cross-process
record leases, and local host notification/authorization hooks. Agent workflows
that require clarification or confirmation still needed a durable interaction
identity instead of creating an unrelated request for every host question.

The feature must remain bounded and compatible with existing records. It must
not imply remote authentication, transport, or exactly-once external effects.

## Decision

Extend `HumanInputRequest` with a bounded `max_rounds` quota, the current
`round_index`, and immutable completed-round history. Existing serialized
requests default to one round and an empty history. `HumanInputRound` retains
the prior prompt, schema, status, and decision without executable objects.

`InMemoryHumanInputStore` and `FileHumanInputStore` expose
`continue_round(interaction_id, prompt, input_schema, actor_id=None)`. The
operation:

1. accepts only a decided request;
2. requires the next round to remain below the request's maximum;
3. validates the new prompt and bounded JSON schema;
4. authorizes the `continue` action before mutation when an authorizer exists;
5. appends the completed round and reopens the same interaction ID as pending;
6. emits a metadata-only `continued` notification after persistence.

File-backed continuation is fenced by the existing per-record lease. If the
notification fails, the persisted pending round remains authoritative and the
typed error tells the caller to inspect before retrying. The agent exposes
`continue_human_input` and includes prior accepted/rejected responses in the
multi-round tool result while preserving the original one-shot response shape
for requests with no history. The durable run checkpoint continues to point at
the same interaction while a caller opens the next round before resuming.

## Consequences

- Same-record clarification and confirmation survives process restart and has
  an explicit maximum-round bound.
- Older records and custom stores remain usable when no continuation is
  requested; custom stores that lack the method return a typed unsupported
  error through the agent helper.
- Round history increases record size, so the existing JSON depth, item, record
  byte, and maximum-round bounds continue to apply.
- Host callers must coordinate `continue_human_input` before resuming a durable
  run if they want the same checkpoint to wait for the next round.
- Remote identity verification, network transport, distributed ownership,
  push delivery, and exactly-once external side effects remain outside this
  local contract.

## Rejected alternatives

- **Create a new interaction ID for every follow-up:** loses durable same-
  interaction history and makes host correlation the caller's responsibility.
- **Allow unlimited rounds:** creates an unbounded persistence and model-input
  surface.
- **Call a remote identity or messaging service from the stores:** introduces
  credentials, network failure modes, and deployment policy outside the
  dependency-free local runtime.
