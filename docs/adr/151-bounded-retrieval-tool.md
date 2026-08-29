# ADR-151: Bounded retrieval and citation tool

**Status:** Accepted for Slice 207 implementation
**Date:** 2026-08-29
**Decision owners:** Chief Architect / Backend / Security / QA / Release

## Context

MAPLE's retrieval layer already supports bounded source documents,
deterministic chunking, lexical/vector backends, source references, and
provider-neutral reranking. Those are library contracts, however. A model
using the ordinary `ToolRegistry` must currently receive a host-written
adapter before it can search a lexical index and inspect citations.

The adapter must not turn retrieval into an implicit network, execution, or
data-disclosure boundary. In particular, source metadata may contain host
fields that are valid for indexing but should not automatically become model
context.

## Decision

Add `create_retrieval_tool()` to the retrieval module. It accepts an existing
lexical `RetrievalBackend` and returns a read-only `Tool` with:

- a required bounded `query` string;
- an optional model-selected `top_k` bounded by the factory configuration;
- deterministic `hits` containing `chunk_id`, `document_id`, `text`, `score`,
  `matched_terms`, and source `uri` plus optional `title`;
- no source/chunk metadata passthrough by default;
- a finite whole-result JSON byte bound; and
- `retrieval` and `read-only` tags with approval disabled by default.

The factory validates configuration up front. Its handler validates UTF-8
query size, invokes the backend, validates the `Result` shape and every hit,
rejects duplicate chunks and non-finite scores, then serializes the complete
result with `allow_nan=False`. Backend exceptions, malformed return values,
and backend errors become generic typed errors without carrying backend
messages or payloads. Oversized output fails rather than truncating a source
or citation.

The first adapter targets the string-query `RetrievalBackend` contract. A
vector tool that calls a host embedding provider is intentionally a separate
decision because it introduces query embedding failure, model selection, and
potential provider/network policy.

## Alternatives considered

1. **Require every host to write its own `Tool` wrapper.** This avoids a new
   public helper but produces inconsistent bounds, result shapes, and error
   disclosure across hosts.
2. **Expose the backend object directly to the model.** This is not a stable
   tool contract and risks exposing mutable/index-specific methods.
3. **Add one factory that accepts both lexical and vector backends.** Their
   query types and score/error contracts differ; combining them would either
   hide embedding policy or weaken type/boundary validation.
4. **Return all source and chunk metadata.** This is convenient but makes
   accidental disclosure the default. URI/title plus bounded text is enough
   for the first citation surface; hosts can write an explicit policy-aware
   tool when metadata is needed.

## Threat sketch and controls

| Threat | Control |
| --- | --- |
| Unbounded model query or result fan-out | UTF-8 query bound, finite top-k bound, backend bounds, and whole-result byte bound. |
| Malformed or hostile backend result | Require `Result`, `RetrievalHit`, `DocumentChunk`, bounded IDs/source, finite score, string terms, unique chunk IDs, and JSON-safe serialization. |
| Backend exception or private data disclosure | Generic typed backend errors; omit source/chunk metadata and raw exception text. |
| Incomplete citation from truncation | Reject oversized complete output instead of silently truncating hit text or source identity. |
| Retrieved-content execution | The adapter only returns data; it never interprets, imports, evaluates, or executes hit text. |
| False semantic/authorization claim | Public docs state that retrieval quality, corpus authorization, source truth, and prompt-injection policy remain host responsibilities. |

## Consequences

Positive consequences:

- lexical RAG is directly usable from MAPLE's normal agent tool loop;
- model-visible results have one stable, bounded citation shape;
- source metadata disclosure is opt-in through a separate host decision; and
- no dependency, network, vector, or execution behavior is added.

Tradeoffs:

- the first factory does not issue vector queries;
- output rejection can require the host to lower `top_k` or chunk sizes; and
- a URI/title is provenance data, not proof that a generated answer is faithful.

## Rollback

Rollback is additive and reversible: remove the factory, exports, tests, and
documentation while leaving all existing retrieval backends unchanged. No
index or source data is deleted.

## Verification

The brief maps the contract to focused retrieval/tool tests. The release gate
also requires the full suite, Black, Ruff, mypy, `compileall`, project-scoped
`pip-audit`, and a clean archived package smoke.
