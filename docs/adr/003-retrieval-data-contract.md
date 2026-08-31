# ADR-003: Dependency-free retrieval and source contract

**Status:** Accepted
**Date:** 2026-08-24
**Decision owners:** Chief Architect / ML Engineer

## Context

MAPLE has memory and state primitives but no native document ingestion,
chunking, retrieval result, or source-citation contract. Agent frameworks
commonly need retrieval-augmented generation while deployments vary in their
embedding model and vector database choices.

## Decision

Add `maple.autonomy.retrieval` with:

- immutable `SourceRef`, `Document`, `DocumentChunk`, and `RetrievalHit` data
  contracts;
- deterministic, bounded text chunking with overlap and character offsets;
- a dependency-free `InMemoryLexicalRetriever` reference implementation using
  normalized token matching and deterministic ranking;
- document, query, result-count, chunk-count, and serialized-size limits;
- source references on every hit so callers can cite retrieved material;
- a backend boundary that can later host embedding/vector adapters.

The reference backend is lexical, not an embedding model. It is intended for
tests, local development, and small trusted datasets; production vector stores
remain adapters and are outside this slice.

## Alternatives considered

1. **Add a vector database dependency:** rejected because it would expand the
  dependency and deployment surface before a stable contract exists.
2. **Expose raw strings only:** rejected because source identity, offsets, and
  metadata are required for grounded agent answers.
3. **Use the existing memory store as retrieval:** rejected because episodic and
  semantic memory have different lifecycle and query semantics.

## Consequences

MAPLE gains a testable RAG boundary without requiring network services or model
credentials. Lexical ranking is intentionally limited; vector/embedding
quality, document loaders, and managed stores remain follow-on adapters.
