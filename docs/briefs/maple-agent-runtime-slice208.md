# Slice 208 brief - host-owned vector retrieval tool

**Date:** 2026-08-29
**Class:** L (new public agent-tool factory crossing embedding and retrieval boundaries)
**Roles:** Product Owner / Chief Architect / Backend / Security / QA / Release

## Problem

MAPLE now has bounded in-memory and durable local vector retrievers, plus a
read-only lexical retrieval/citation tool. A model still cannot request vector
search through the normal `ToolRegistry` loop unless the host writes its own
embedding-and-retrieval adapter. That leaves the vector RAG path below the
lexical path in tool ergonomics and produces no common citation boundary.

## Scope

- In: a public `create_vector_retrieval_tool()` factory; a caller-owned
  `EmbeddingProvider` seam; bounded string query and result-count parameters;
  delegation to an existing vector retriever; reuse of the metadata-minimal
  citation result shape and output byte bounds from `create_retrieval_tool()`;
  generic provider/backend/result errors; public exports; focused regressions;
  API/README/parity/changelog and release bookkeeping.
- Out: selecting or implementing an embedding model; provider dependencies;
  network calls; retries, caching, batching, streaming, async provider
  protocols, managed stores, corpus authorization, source metadata passthrough,
  reranking, retrieved-content execution, prompt-injection filtering claims,
  remote transport, and distributed coordination.
- Deferred: async embedding, provider-specific capability routing, embedding
  version/index migration, and policy-aware corpus authorization require
  separate contracts.

## Constraints and assumptions

- The host supplies an object exposing `embed(text) -> Result[Sequence[float],
  Error]` and a vector backend exposing `search(query_vector, top_k=...)`.
  MAPLE invokes those callbacks but does not select a provider or make a
  network request.
- The factory validates the model-visible text query and `top_k`; the existing
  vector backend remains authoritative for vector dimensions, index limits,
  and similarity scores.
- Vector hits are normalized to the existing retrieval-tool citation contract:
  bounded chunk/document IDs, text, finite score, an empty `matched_terms`
  array, and source URI plus optional title. Source and chunk metadata remain
  omitted by default.
- Provider and backend exceptions, malformed `Result` values, invalid vectors,
  and backend errors become generic typed errors. Private exception text,
  paths, vectors, and provider payloads do not cross the tool boundary.
- The returned tool is read-only and does not require approval by default. A
  host can request approval through the factory option when local policy needs
  it.

## Acceptance criteria

1. Valid configuration returns a `Tool` with a bounded query/top-k schema,
   deterministic vector-citation description, retrieval/read-only tags, and
   the requested approval setting. Invalid backend/provider/name/bounds
   configuration fails fast.
2. A valid provider vector and vector-backend result become the same bounded,
   JSON-safe `hits` envelope as the lexical retrieval tool, with
   `matched_terms=[]` and source metadata limited to URI/title.
3. Empty/control/oversized queries, invalid top-k values, provider errors,
   malformed provider results, vector-backend errors, malformed hits,
   non-finite scores, duplicate chunks, and oversized output fail closed
   without returning a partial hit list.
4. Provider and backend exception/error payloads are normalized to generic
   bounded errors without leaking private messages, paths, vectors, or raw
   payloads. No provider callback is retried or called more than once per tool
   invocation.
5. The factory is importable from `maple.autonomy` and `maple`; public docs
   describe the exact host-owned embedding and local vector-query boundary.
   No network, execution, managed-store, or hosted capability claim is added.
6. Focused retrieval/tool regressions, the full suite, static gates,
   project-scoped dependency audit, and clean package smoke remain green.

## Release and safety boundary

This is a local adapter over caller-owned embedding and vector-index
contracts. It does not prove source truth, semantic faithfulness, citation
correctness, prompt-injection resistance, embedding quality, or authorization
to access the corpus. Hosts remain responsible for provider credentials,
network policy, rate limits, privacy, corpus access, and approval decisions.
Existing CI-policy, execution-isolation, hosted-coordination, dependency, and
publication gates remain independent.
