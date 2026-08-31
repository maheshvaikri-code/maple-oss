# ADR-015: Dependency-free vector retrieval seam

## Status

Accepted — 2026-08-24

## Context

MAPLE already had bounded document chunking, source references, and a local
lexical retriever. Leading agent frameworks also expose embedding/vector
retrieval, but adding a hosted embedding model or vector database would add a
provider dependency, credentials, and deployment policy before the core
contract is stable.

## Decision

Add `InMemoryVectorRetriever`, which accepts caller-supplied embeddings for
each generated document chunk and ranks source-bearing chunks with cosine
similarity.

- The caller owns embedding generation through the optional
  `EmbeddingProvider` protocol; MAPLE does not call a model or vendor.
- Vectors are finite numeric sequences with bounded dimensions and non-zero
  norm. A document must provide exactly one vector per generated chunk.
- One index has one dimension. Dimension changes, vector count overflow,
  invalid inputs, and duplicate documents fail before mutation.
- Results use deterministic score-descending and chunk-ID tie ordering and
  retain the existing `DocumentChunk`/`SourceRef` citation boundary.
- The in-memory index is thread-safe within one process and bounded by document,
  vector, dimension, and result limits. Persistence, ANN acceleration, and
  provider-specific embedding adapters remain follow-on work.

## Alternatives considered

### Add a vector database dependency

Deferred because it would expand runtime dependencies, deployment, credentials,
and audit scope before MAPLE has a stable vector contract.

### Implement a homegrown embedding model

Rejected. Model quality, tokenization, model pinning, and evaluation would be
misrepresented by a simplistic local implementation.

### Store vectors without source-bearing chunks

Rejected because retrieval without stable source identity would weaken grounded
answering and citation integrity.

## Consequences

Hosts can plug in a model or existing embedding pipeline while using a bounded,
tested MAPLE index locally. The slice proves vector contract behavior and
retrieval ranking, not embedding quality, recall across a production corpus,
ANN performance, persistence, or RAG generation groundedness.
