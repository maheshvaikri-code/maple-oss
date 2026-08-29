# Slice 209 brief - async host-owned vector retrieval tool

**Date:** 2026-08-29
**Class:** L (new public async provider/tool contract)
**Roles:** Product Owner / Chief Architect / Backend / Security / QA / Release

## Problem

Slice 208 makes synchronous host-owned embedding callable through a bounded
vector retrieval tool. Hosts whose embedding service is asynchronous still
need a wrapper and may otherwise block an agent event loop while adapting the
provider. MAPLE already supports `Tool.execute_async()` and async model turns,
but the vector RAG surface does not expose an async embedding seam.

## Scope

- In: a public `AsyncEmbeddingProvider` protocol; a public
  `create_async_vector_retrieval_tool()` factory; bounded query/top-k/output
  behavior matching the synchronous vector tool; one awaited provider call;
  executor-backed synchronous vector search; shared citation serialization;
  explicit async-only sync behavior; exports, tests, docs, and release
  evidence.
- Out: provider/model selection; provider dependencies; network calls made by
  MAPLE; retries, caching, batching, streaming, cancellation of a provider
  that ignores cancellation, managed stores, corpus authorization, source
  metadata passthrough, reranking, retrieved-content execution, prompt-
  injection filtering claims, remote transport, and distributed coordination.
- Deferred: provider capability routing, embedding version/index migration,
  async vector-backend protocols, and policy-aware corpus authorization need
  separate contracts.

## Constraints and assumptions

- The host supplies an awaitable `embed(text) -> Result[Sequence[float],
  Error]` and a vector backend exposing synchronous
  `search(query_vector, top_k=...)`. MAPLE awaits the provider once and runs
  the backend call in the event loop's default executor; MAPLE selects neither
  a model nor a network policy.
- `execute_async()` is the supported call path. Direct synchronous
  `execute()` returns a typed async-required error and never invokes the
  provider or backend.
- Provider vectors are validated for bounded dimensions, finiteness, and
  non-zero content before backend delegation. Vector hits use the same
  metadata-minimal citation envelope as the sync and lexical tools, including
  `matched_terms=[]` and source URI plus optional title.
- Provider/backend exceptions, malformed `Result` values, invalid vectors,
  malformed hits, and output overflow fail closed without raw exception text,
  vectors, paths, or private payloads.

## Acceptance criteria

1. Valid configuration returns an async-capable read-only `Tool` with the
   bounded vector query/top-k schema, retrieval tags, and requested approval
   setting. Invalid backend/provider/name/bounds configuration fails fast.
2. `await tool.execute_async(...)` awaits the provider once, delegates one
   bounded vector search without blocking the event loop, and returns the
   shared deterministic citation envelope without exposing embeddings.
3. Direct `tool.execute(...)` fails with `RETRIEVAL_TOOL_ASYNC_REQUIRED` and
   performs no provider/backend work. Invalid query/top-k values are rejected
   before provider invocation.
4. Provider/backend failures, malformed provider results or vectors,
   malformed/duplicate/non-finite hits, and oversized output fail closed
   without partial hit lists or private error disclosure.
5. The protocol and factory are importable from `maple.autonomy` and `maple`.
   Public docs describe the async-only, host-owned embedding boundary. No
   network, execution, managed-store, or hosted capability claim is added.
6. Focused async retrieval regressions, the full suite, static gates,
   project-scoped dependency audit, and clean package smoke remain green.

## Release and safety boundary

This is a local async adapter over caller-owned embedding and vector-index
contracts. It does not prove provider availability, embedding quality, source
truth, semantic faithfulness, citation correctness, prompt-injection
resistance, or authorization to access the corpus. Hosts remain responsible
for provider credentials, network policy, rate limits, privacy, corpus access,
and cancellation behavior. Existing CI-policy, execution-isolation,
hosted-coordination, dependency, and publication gates remain independent.
