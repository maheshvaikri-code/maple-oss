# ADR-093: Fail-Closed Episodic Search

## Status

Accepted for preview release readiness.

## Context

`EpisodicMemory.search()` searched every retained event but treated state-list
and state-read failures as empty results. It also accepted arbitrary query
sizes and result limits, allowing caller input to expand matching work and
result memory without a contract. An incomplete search presented as a
successful empty result is unsafe for agent memory decisions.

## Decision

Keep local keyword search and add a bounded, fail-closed input and state
boundary:

- queries must be text without Unicode control characters and at most `4,096`
  UTF-8 bytes;
- `limit` must be an integer from `1` through `1,000` and boolean values are
  rejected;
- list and read errors from `StateStore` are propagated unchanged;
- malformed stored histories return `EPISODIC_STATE_INVALID`;
- valid matches stop at the requested limit and preserve existing local
  case-insensitive substring behavior.

The search remains an in-process keyword scan over per-task retained events.
It does not add an index, semantic ranking, distributed coordination, retry,
or hidden fallback.

## Alternatives considered

| Alternative | Reason not selected |
|---|---|
| Continue returning an empty result on store errors | It hides incomplete state and can cause an agent to infer that no memory exists. |
| Accept arbitrary query and limit values | It leaves CPU, string-processing, and result allocation dependent on unbounded caller input. |
| Add a semantic or distributed search index | It expands storage, provider, consistency, and dependency scope beyond this local hardening slice. |
| Bound local keyword search and propagate every state failure | Selected: preserves the existing useful behavior while making limits and failure semantics explicit. |

## Consequences

Positive consequences:

- Query and result allocations have explicit caller-facing bounds.
- Search failures remain observable and are not misrepresented as empty memory.
- Malformed persisted state fails closed rather than being partially interpreted.
- Existing successful keyword matching remains dependency-free and local.

Negative consequences and boundaries:

- Search still scans the available task keys and is not an indexed query;
  hosts remain responsible for bounding the number of task keys in a store.
- The result order remains store/key/event traversal order, not relevance order.
- No semantic retrieval, distributed search, retry, or automatic repair is
  introduced.

## Failure modes

`EPISODIC_QUERY_INVALID` identifies invalid or oversized query text.
`EPISODIC_SEARCH_LIMIT_INVALID` identifies an invalid result limit.
`StateStore` list/read errors and `EPISODIC_STATE_INVALID` are returned to the
caller. No search failure is converted into a successful empty result.

## Evidence

Focused memory regressions cover invalid query/limit input, state list/read
error propagation, malformed history, and existing successful search behavior.
Full release evidence is recorded in the slice 148 QA and review records.
