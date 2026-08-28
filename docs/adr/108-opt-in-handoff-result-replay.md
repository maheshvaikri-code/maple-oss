# ADR-108: Opt-in local replay for durable handoff results

**Date:** 2026-08-28
**Status:** accepted
**Deciders:** Chief Architect

## Context

`HandoffStore` currently records bounded identity and ownership transitions,
but completed records retain only the target goal ID. The local agent-as-tool
surface can already reuse a successful bounded result through a parent
execution journal. Durable handoffs need an equivalent recovery path, but
storing child output by default would expand the data-retention and remote
exposure boundary.

## Decision

Add an optional `result` mapping to `HandoffRecord`. The built-in stores accept
that mapping only on `complete(..., result=...)`, validate it as finite,
JSON-compatible, and bounded data, and preserve it through local file restart.
The field is optional in `from_dict` for compatibility with records written
before this decision.

`create_handoff_tool` gains `persist_result=False` and an optional explicit
`handoff_id` tool argument. When persistence is enabled, the factory requires
an attached store whose `complete` method supports the optional result
keyword. A retry addressing a completed record with a valid stored result
returns that result without invoking the target. New IDs retain generated-ID
behavior; accepted, failed, or result-less records do not silently replay.

Remote serialization calls `HandoffRecord.to_dict(include_result=False)` so
the authenticated handoff API remains digest-only. Local `to_dict()` retains
the result for store persistence and defensive copy operations.

## Data flow and failure modes

```text
explicit handoff_id + task/context
  -> bounded identity digest check
  -> local HandoffStore lookup/create
  -> completed + valid result: replay bounded result
  -> otherwise pending -> accepted -> target
  -> completed(result) or failed(error_type)
```

- A task/context mismatch for an existing ID is rejected by the store before
  target execution.
- A completed record without a stored result returns a typed replay-unavailable
  error rather than invoking a target with ambiguous ownership history.
- Result validation and record-size limits fail before file replacement.
- Replay is local and successful-result-only; a crash before persistence can
  still repeat an external effect.

## Consequences

- Local callers can recover a completed handoff result after restart without a
  second specialist invocation.
- Result retention is explicit, bounded, and host-owned; default handoffs
  remain digest-only locally and remotely.
- Custom legacy stores remain compatible when result persistence is disabled;
  enabling it requires an explicit extended completion signature.
- This does not restore an in-flight child run, coordinate remote payloads, or
  claim exactly-once effects.

## Alternatives considered

| Option | Pros | Cons | Why not |
|---|---|---|---|
| Optional bounded result with explicit ID and remote redaction (chosen) | Reuses the tested handoff state machine; additive and opt-in | Requires deliberate retention and caller ID | Meets local recovery need without widening default exposure |
| Persist every handoff result | Simplifies callers | Stores sensitive output by default and changes remote risk | Violates least-retention boundary |
| Replay by task/context digest alone | No new input field | Collides across separate handoffs and cannot express intent | Identity must include an explicit caller-owned handoff ID |
| Add a new child-run database | Richer recovery | New protocol, ownership, migration, and reconciliation surface | Deferred until a first-class child lifecycle is designed |

**Invalidation triggers:** a reviewed child-run restore protocol, remote result
delivery contract, or host retention/encryption policy would reopen this ADR.
