# Slice 206 brief - durable local vector retrieval

**Date:** 2026-08-29  
**Class:** L (new public retrieval backend, durable schema, and storage/security boundary)  
**Roles:** Product Owner / Chief Architect / Backend / Security / QA / Release

## Problem

MAPLE now has a bounded durable local lexical index, while
`InMemoryVectorRetriever` still loses caller-supplied embeddings when its
process exits. A local RAG host therefore has to rebuild vector state after a
restart even when it has already paid the cost of producing embeddings. The
local retrieval contract should offer the same restart-safe source-of-truth
behavior for lexical and vector paths without implying a managed vector
database or hosted embedding service.

## Scope

- In: a bounded `FileVectorRetriever` using the existing `Document`,
  `TextChunker`, and `InMemoryVectorRetriever` contracts; atomic JSON
  persistence of validated source documents and per-chunk caller-supplied
  vectors; restart reconstruction; add/remove/search/stats; local
  cross-process fencing; fail-closed corruption, size, policy, and dimension
  checks; public exports; API/README/parity/changelog updates; and regression
  tests.
- Out: embedding generation, model selection, network fetching, managed
  vector databases, vector indexes optimized for large-scale serving,
  distributed replication or consensus, connector/checkpoint transactions,
  background ingestion, compaction, vector encryption, and semantic ranking.
- Deferred: hosted retrieval coordination, provider adapters, transactional
  ingestion, and an optimized on-disk ANN format require separate contracts.

## Constraints and assumptions

- The file envelope is versioned, JSON-only, byte-bounded, and stores the
  validated chunking policy plus each source `Document` and its validated
  per-chunk vectors. Chunks and vector lookup maps remain deterministic
  derived state rebuilt through `InMemoryVectorRetriever`.
- One embedding is required for every generated chunk. Non-empty indexed
  documents share one vector dimension; an empty document may have no chunks
  and therefore contributes no dimension. Dimensions and vector values are
  validated on both ingress and reload.
- Every public operation refreshes from the file under a process lock and the
  existing `DurableRecordLease`. The file boundary provides local
  cross-process serialization, not distributed consensus.
- Writes validate a prospective in-memory candidate, flush and `fsync` a
  same-directory temporary file, then atomically replace the state file. A
  rejected or failed operation leaves the prior file and visible state
  unchanged.
- No runtime dependency is added. Existing vector validation, cosine scoring,
  source-reference, and result/error contracts remain authoritative.

## Acceptance criteria

1. `FileVectorRetriever` accepts only bounded directory, byte, lease, vector,
   dimension, and result configuration; malformed configuration or an
   existing corrupt, oversized, invalid-UTF-8, or incompatible file fails
   before exposing a partial index. Proven by
   `test_file_vector_retriever_rejects_invalid_configuration` and
   `test_file_vector_retriever_rejects_corrupt_oversized_or_mismatched_state`.
2. Adding a valid document and one vector per generated chunk atomically
   persists a bounded versioned envelope, returns deterministic chunks, and a
   newly constructed retriever can search the same source after restart.
   Proven by `test_file_vector_retriever_persists_and_reloads_embeddings`.
3. Invalid vector counts, vector dimensions, and duplicate documents are
   rejected without changing the durable file. Removing a document persists
   the deletion, returns `False` for an absent document, and a failed
   candidate write preserves the prior searchable state. Proven by
   `test_file_vector_retriever_rejects_vector_dimension_mismatch_without_mutation`
   and `test_file_vector_retriever_remove_persists_and_is_fail_closed`.
4. Concurrent retriever instances sharing one directory serialize mutations
   through the durable lease and do not silently overwrite a completed peer
   update. Proven by
   `test_file_vector_retriever_serializes_shared_directory_mutations`.
5. Search and stats refresh from the durable source, preserve deterministic
   score/chunk ordering, enforce query and result bounds, and treat missing
   state as an empty index. Proven by
   `test_file_vector_retriever_refreshes_external_updates_and_bounds_queries`.
6. Non-JSON metadata, malformed vector records, unsupported schema versions,
   non-finite values, and persistence failures return typed errors or the
   documented constructor error without leaking raw paths, payloads, or
   exception details. Proven by
   `test_file_vector_retriever_rejects_non_json_documents_and_redacts_storage_failures`.
7. The public import, API example, documentation, retrieval suite, full test
   suite, static gates, project dependency audit, and clean package smoke
   remain green. No managed-store, network, distributed, or semantic-ranking
   claim is added.

## Release and safety boundary

This is a local durable vector backend with caller-owned embeddings and
at-least-once rebuild semantics: the persisted source/vector records are the
authority for a successful mutation, and the searchable index is rebuilt
derived state. It is not an embedding provider, distributed index,
transaction with connector ingestion, managed vector database, or guarantee
of semantic relevance. Existing execution-isolation, hosted-coordination,
CI-policy, dependency, and publication gates remain independent.

