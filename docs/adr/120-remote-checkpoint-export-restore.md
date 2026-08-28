# ADR-120: Authenticated remote durable checkpoint export and restore

**Date:** 2026-08-28 · **Status:** accepted
**Deciders:** Chief Architect

## Context

MAPLE has bounded in-memory and file-backed `AgentRunStore` implementations,
native sync/async resume, and an authenticated control plane for redacted run
inspection and metadata history. The existing remote adapter intentionally
keeps checkpoint contents on the owning host, leaving compatible hosts unable
to transfer a paused or running durable cursor through a typed contract.

The checkpoint contains conversation messages, reasoning trace, tool-call
arguments, pending interaction identifiers, and result state. It therefore
cannot be treated as ordinary read-only run metadata. A restore operation must
also avoid replacing a newer destination cursor or crossing agent ownership.

## Decision

Add two authenticated routes and additive client methods:

- `GET /v1/agents/{agent_id}/runs/{run_id}/checkpoint` exports the complete
  validated `AgentRunCheckpoint` under the dedicated `agent:restore` scope.
- `POST /v1/agents/{agent_id}/runs/{run_id}/restore` accepts one complete
  checkpoint plus an optional `expected_version`, validates it before store
  mutation, and returns a metadata-only receipt.

The wire representation is the existing `AgentRunCheckpoint.to_dict()` JSON
shape. The server parses it with `AgentRunCheckpoint.from_dict()` and never
deserializes Python objects, imports code, or invokes a handler. Only `running`
and `paused` checkpoints are restorable because terminal cursors cannot be
resumed. The route and checkpoint must agree on both `agent_id` and `run_id`.

When a destination record exists, the server first verifies its agent
identity, then delegates the exact `expected_version` to the configured
`AgentRunStore.save()` CAS boundary. Omitting `expected_version` is therefore
safe for a new record and conflicts with an existing record. The client does
not retry automatically; callers must choose their retry and side-effect
policy.

## Alternatives considered

| Option | Pros | Cons | Why not |
|---|---|---|---|
| Full JSON export plus CAS restore (chosen) | Uses existing schema/store contract; detached and testable | Transfers sensitive state; requires explicit scope and host policy | Best bounded bridge between compatible host-owned stores |
| Metadata-only inspection | Lowest disclosure | Cannot reconstruct a resume cursor | Already exists and does not close remote restore |
| Opaque server-to-server store replication | Could hide checkpoint fields from callers | Couples hosts, adds deployment/auth/discovery semantics | Requires a separate hosted/distributed contract |
| Pickle or executable snapshot transfer | Could preserve arbitrary runtime objects | Code execution and compatibility risk | Violates the fail-closed persistence boundary |

## Consequences

- Positive: compatible hosts can transfer non-terminal durable agent state and
  then use the existing native resume boundary.
- Positive: authorization and version fencing are explicit and least-privilege.
- Negative: checkpoint contents may include sensitive prompts, tool arguments,
  and results; hosts must provide TLS, retention, and principal governance.
- Negative / debt accepted: this is not distributed scheduling, push delivery,
  automatic retry, or exactly-once external-effect coordination.
- Invalidation trigger: adding hosted identity, encrypted transfer, a
  distributed checkpoint service, or a different checkpoint schema requires a
  new contract and review.
