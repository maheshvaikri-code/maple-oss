# ADR-153: Async vector retrieval tool with host-owned embeddings

**Status:** Accepted for Slice 209 implementation
**Date:** 2026-08-29
**Decision owners:** Chief Architect / Backend / Security / QA / Release

## Context

MAPLE's vector retrieval tool now supports synchronous host-owned embedding,
but asynchronous embedding providers need an event-loop-safe public boundary.
`Tool.execute_async()` already supports native async handlers and uses a worker
for legacy synchronous tools. The missing contract is the provider seam and
the decision about where synchronous local vector search runs.

The adapter must not select a model, credentials, network behavior, retries,
or corpus policy. It must also share the existing bounded citation boundary so
lexical, synchronous-vector, and asynchronous-vector tools cannot drift in
result disclosure or error handling.

## Decision

Add `AsyncEmbeddingProvider` and `create_async_vector_retrieval_tool()`.
The factory accepts a caller-owned async provider and an existing vector
retriever, and returns a read-only `Tool` with:

- a required bounded `query` and optional bounded `top_k`;
- one awaited provider call per `execute_async()` invocation;
- provider-vector validation before backend invocation;
- one synchronous vector-backend search executed in the event loop's default
  executor, preserving responsiveness without adding an async backend
  protocol;
- deterministic `hits` with `chunk_id`, `document_id`, `text`, finite `score`,
  empty `matched_terms`, and source URI plus optional title;
- no embedding vector, source metadata, or chunk metadata passthrough;
- the existing whole-result UTF-8 byte limit and generic error boundary; and
- `retrieval` and `read-only` tags with approval disabled by default.

The returned tool is explicitly async-only. Its normal `execute()` method
returns `RETRIEVAL_TOOL_ASYNC_REQUIRED` without invoking provider or backend;
`execute_async()` performs argument validation before awaiting the provider and
then applies the common citation result schema. A provider that needs custom
cancellation, batching, retries, or policy must be adapted by the host under
an explicit contract.

## Alternatives considered

1. **Run the async provider synchronously.** This risks event-loop blocking or
   unsafe nested-loop behavior and hides the provider's async contract.
2. **Add an async method to the existing sync factory.** This makes sync and
   async provider errors and call semantics ambiguous and weakens typing.
3. **Add a required async vector-backend protocol.** Existing local backends
   are synchronous and bounded; forcing a second backend surface expands the
   slice without closing the provider gap.
4. **Use a new provider dependency or built-in embedding model.** This would
   make MAPLE choose model, credential, network, and retry policy.
5. **Duplicate the citation serializer.** This risks inconsistent metadata,
   bounds, and error disclosure across retrieval tools; the async factory
   reuses the existing serializer boundary.

## Threat sketch and controls

| Threat | Control |
| --- | --- |
| Event-loop blocking from local backend | Execute the synchronous vector search in the default executor. |
| Unbounded query or result fan-out | Existing UTF-8 query, top-k, vector, hit, and whole-output bounds. |
| Provider/backend private-data disclosure | Generic errors; no raw exception text, vectors, paths, or payloads. |
| Malformed provider vector | Validate dimensions, finiteness, and non-zero content before backend invocation. |
| Malformed or hostile hit | Shared serializer requires bounded source-bearing hits, finite scores, unique chunks, and JSON-safe output. |
| Async provider side effects after cancellation | MAPLE only controls its await boundary; provider cancellation and external effects remain host-owned. |
| False semantic/authorization claim | Public docs identify embedding quality, source truth, corpus access, prompt-injection policy, and faithfulness as host responsibilities. |

## Consequences

Positive consequences:

- async embedding services can plug into the normal async agent/tool loop;
- the event loop is not blocked by the existing synchronous vector backends;
- sync and async vector tools share one citation/error/output boundary; and
- no dependency, network, execution, or managed-store behavior is added.

Tradeoffs:

- the provider must be awaitable and the tool must be called asynchronously;
- vector-backend search still uses a default-executor worker rather than an
  async backend protocol; and
- MAPLE does not cancel a provider that ignores cancellation or claim exactly-
  once external effects.

## Rollback

Rollback is additive and reversible: remove the protocol, factory, exports,
tests, and documentation while leaving synchronous vector tools, providers,
indexes, and backends unchanged. No index or source data is deleted.

## Verification

The brief maps the contract to focused async retrieval/tool tests. The release
gate also requires the full suite, Black, Ruff, mypy, `compileall`,
project-scoped `pip-audit`, and a clean archived package smoke.
