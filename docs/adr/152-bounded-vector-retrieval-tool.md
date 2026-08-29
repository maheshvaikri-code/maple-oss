# ADR-152: Bounded vector retrieval tool with host-owned embeddings

**Status:** Accepted for Slice 208 implementation
**Date:** 2026-08-29
**Decision owners:** Chief Architect / Backend / Security / QA / Release

## Context

MAPLE's retrieval layer supports bounded source documents, deterministic
chunking, caller-supplied vectors, local cosine retrieval, durable local
vector indexes, and a lexical retrieval tool. The vector path still requires
each host to write its own model-tool wrapper: the model query must be turned
into a vector before the vector backend can be called.

The wrapper must not quietly become a model-provider or data-access policy.
Embedding selection, credentials, network behavior, rate limits, corpus
authorization, and semantic quality belong to the host. The tool boundary must
also retain the existing citation serializer's limits and metadata-minimal
disclosure policy.

## Decision

Add `create_vector_retrieval_tool()` to the retrieval module. It accepts a
caller-owned `EmbeddingProvider` and an existing vector retriever, and returns
a read-only `Tool` with:

- a required bounded `query` string;
- an optional model-selected `top_k` bounded by factory configuration;
- one synchronous provider call followed by one vector-backend search per
  invocation;
- deterministic `hits` containing `chunk_id`, `document_id`, `text`, finite
  `score`, an empty `matched_terms` array, and source `uri` plus optional
  `title`;
- no source/chunk metadata or embedding vector passthrough;
- the same finite whole-result JSON byte bound as the lexical tool; and
- `retrieval` and `read-only` tags with approval disabled by default.

The implementation uses a private string-query adapter that calls the host
provider, validates that it returned a `Result`, calls the vector retriever,
and normalizes each `VectorRetrievalHit` into the existing
`create_retrieval_tool()` input contract. The existing serializer therefore
owns query, hit, duplicate, score, UTF-8, JSON, and output-size validation.
Provider/backend exceptions and error values are hidden behind the generic
retrieval-tool backend error boundary.

The factory accepts synchronous providers only in this slice. `Tool`'s normal
executor-backed async path can run the complete synchronous handler without
inventing an async provider protocol; a provider that itself needs async I/O
must be adapted by the host under an explicit future contract.

## Alternatives considered

1. **Require every host to write an embedding/tool wrapper.** This preserves
   the current surface but yields inconsistent limits, citation shapes, and
   error disclosure.
2. **Add a provider dependency or built-in model.** This would make MAPLE
   choose credentials, model/version, network behavior, and failure policy.
3. **Let the model submit vectors directly.** This exposes an index-specific
   implementation detail, makes prompt/tool input unreasonably large, and
   bypasses the host's embedding policy.
4. **Expand `create_retrieval_tool()` to accept lexical and vector backends.**
   Their query types and hit contracts differ; a combined API would hide the
   embedding boundary and weaken type and error validation.
5. **Return vector scores or metadata without the shared serializer.** This
   would duplicate the security-sensitive citation boundary and risk drift
   between lexical and vector tools.

## Threat sketch and controls

| Threat | Control |
| --- | --- |
| Unbounded model query or result fan-out | UTF-8 query bound, finite top-k bound, existing vector-index bounds, and whole-result byte bound. |
| Provider or backend private-data disclosure | Generic provider/backend errors; no raw exception text, vectors, payloads, or metadata passthrough. |
| Malformed or hostile provider result | Require a `Result`; vector backend validates dimensions, finiteness, and limits; outer tool rejects failed or malformed results. |
| Malformed or hostile retrieval result | Shared serializer requires source-bearing retrieval hits, bounded identifiers/text, finite scores, unique chunks, and JSON-safe output. |
| Partial or misleading citations | Reject oversized complete output rather than truncating hits or source identity. |
| Retrieved-content execution | The adapter only returns data; it never interprets, imports, evaluates, or executes hit text. |
| False semantic/authorization claim | Public docs identify embedding quality, source truth, corpus access, prompt-injection policy, and faithfulness as host responsibilities. |

## Consequences

Positive consequences:

- vector RAG is directly usable from MAPLE's normal agent tool loop;
- lexical and vector tools share one bounded citation envelope;
- provider/model policy remains explicit and host-owned; and
- no dependency, network, execution, or managed-store behavior is added.

Tradeoffs:

- only synchronous host providers are supported;
- the vector tool exposes no model-controlled `min_score` in this slice;
- embedding work runs as part of the tool handler and is not retried; and
- a URI/title is provenance data, not proof that a generated answer is
  faithful.

## Rollback

Rollback is additive and reversible: remove the factory, exports, tests, and
documentation while leaving vector indexes, providers, and existing retrieval
backends unchanged. No index or source data is deleted.

## Verification

The brief maps the contract to focused retrieval/tool tests. The release gate
also requires the full suite, Black, Ruff, mypy, `compileall`, project-scoped
`pip-audit`, and a clean archived package smoke.
