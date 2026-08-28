# ADR-104: Authenticated agent-run history transport

**Status:** Accepted

## Context

Slice 158 added bounded history to the built-in agent-run stores, but the
authenticated local control plane can inspect only the latest run summary.
That leaves a host operator or a separately hosted `RunClient` unable to see
the bounded version progression without direct access to the store.

The existing agent inspection route deliberately omits messages and reasoning
steps. A history route must preserve that boundary: checkpoint results and
errors can contain user or tool data, and returning them for every version
would turn an operational inspection endpoint into a trace export surface.

## Decision

Add an additive read-only route:

```text
GET /v1/agents/{agent_id}/runs/{run_id}/history?limit={N}
```

`limit` is optional and defaults to 100; explicit values must be integers from
1 through 100. The server requires the existing `agent:read` scope and bearer
authentication boundary. It verifies the current checkpoint exists and belongs
to `{agent_id}` before reading history. A store that implements the optional
`AgentRunHistoryStore` contract is queried for its bounded history and the
newest `N` snapshots are returned in ascending checkpoint-version order.

Each response item contains only bounded operational metadata: run and agent
identity, status, step counters, pending interaction IDs, session correlation,
token usage, version, and timestamps. It omits description, result, error,
messages, and reasoning steps. The response envelope is
`{"history": [...]}`. `RunClient.inspect_agent_run_history()` validates the
same IDs and limit before making the request.

Legacy custom stores that implement only `AgentRunStore` remain valid for the
existing latest-summary, resume, and cancellation routes. The new route
returns `AGENT_RUN_HISTORY_UNAVAILABLE` with HTTP 501 for those stores. Missing
stores return `AGENT_RUN_STORE_UNAVAILABLE` (503), missing or cross-agent runs
return `AGENT_RUN_NOT_FOUND` (404), malformed query parameters return
`AGENT_RUN_HISTORY_LIMIT_INVALID` (400), and store/history corruption errors
propagate through the existing typed error mapping.

The route is inspection-only. It does not restore a checkpoint, replay a
handler, consume an approval or input record, expose a trace, or claim remote
history durability beyond the configured store.

## Data flow and failure modes

```text
authenticated GET
  -> path/query bounds and agent:read scope
  -> current checkpoint load and agent ownership check
  -> optional history capability check
  -> bounded store history read
  -> identity validation + newest-N selection
  -> metadata-only JSON response
```

- Authentication and authorization fail before store access.
- A missing store or unsupported optional history capability is explicit; it
  never becomes an empty history response.
- A missing or cross-agent current checkpoint is masked as not found. Any
  history item with a different run or agent identity is an internal
  `AGENT_RUN_HISTORY_INVALID` failure and is not serialized.
- Query limits, path limits, store bounds, and the existing response-byte cap
  bound resource use. The route performs no retry and has no side effect.

The transport does not add a new dependency, persistence mechanism, or
cross-process lease. The configured store remains the authority for ordering,
retention, and corruption handling.

## Alternatives considered

- **Return full checkpoint data for every version:** rejected because results,
  errors, and descriptions can contain sensitive application data and would
  bypass the existing redacted inspection boundary.
- **Add remote restore/time-travel execution:** rejected for this slice because
  restoring a cursor requires explicit handler side-effect, approval replay,
  idempotency, and authorization policy; it is a larger execution contract.
- **Introduce a separate `agent:history` scope:** rejected as unnecessary
  breaking authorization friction for a read-only subset of existing agent
  inspection. The established `agent:read` scope is retained; hosts that need
  finer policy can place the route behind a separate server or principal.

## Revisit triggers

Reopen this decision if remote history must include trace/result payloads,
support arbitrary version selection or restore, require distributed history
search, or need a distinct principal/tenant policy.
