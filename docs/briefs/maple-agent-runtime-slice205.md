# Slice 205 brief - durable local lexical retrieval

**Date:** 2026-08-29
**Class:** L (new public retrieval backend and durable storage boundary)
**Roles:** Product Owner / Chief Architect / Backend / Security / QA / Release

## Problem

MAPLE can persist a connector cursor and can retrieve from bounded in-memory
lexical or vector indexes, but a process restart discards the indexed lexical
documents. A host must rebuild the index before local RAG can answer the same
queries, and two local processes cannot share one durable lexical source of
truth. This leaves the local retrieval contract weaker than the existing
durable session, run, event, and task primitives.

## Scope

- In: a bounded `FileLexicalRetriever` using the existing document/chunk
  contract, atomic JSON persistence of source documents, local cross-process
  fencing, restart-safe add/remove/search/stats behavior, fail-closed load and
  save errors, public exports, API/README/parity/changelog updates, and
  regression tests.
- Out: vector-index persistence, managed vector stores, embedding providers,
  network fetching, connector/checkpoint transactions, distributed
  replication, background ingestion, compaction, and semantic ranking.
- Deferred: a file-backed vector index and managed-store adapters require a
  separate capacity/format decision; hosted retrieval remains gated.

## Constraints and assumptions

- The file envelope is JSON-only, versioned, bounded, and contains the
  validated chunking policy and source `Document` records; chunks and lexical
  term indexes are deterministic derived state and are rebuilt in memory.
- Each public operation refreshes from the file under a local lock and a
  `DurableRecordLease`, so concurrent local instances observe one file-backed
  source of truth. The file boundary is local and does not claim distributed
  consensus.
- Writes use prospective validation, `fsync`, and atomic replacement. A
  rejected or failed persistence operation leaves the prior file and visible
  in-memory index unchanged.
- Existing `TextChunker`, `InMemoryLexicalRetriever`, `Document`, and
  `SourceRef` contracts remain authoritative. No runtime dependency is added.

## Acceptance criteria

1. A file-backed retriever accepts only bounded directory, byte, lease, and
   index-limit configuration; malformed configuration or an existing corrupt,
   oversized, or incompatible file fails before exposing a partial index.
   Proven by `test_file_lexical_retriever_rejects_invalid_configuration` and
   `test_file_lexical_retriever_rejects_corrupt_or_oversized_state`.
2. Adding a valid document returns its deterministic chunks, writes a bounded
   versioned envelope atomically, and a newly constructed retriever can search
   the same source after restart. Proven by
   `test_file_lexical_retriever_persists_and_reloads_documents`.
3. Removing a document persists the deletion, returns `False` for an absent
   document, and a failed candidate write leaves the previous searchable state
   and file bytes unchanged. Proven by
   `test_file_lexical_retriever_remove_persists_and_is_fail_closed`.
4. Concurrent retriever instances sharing one directory serialize mutations
   through the existing durable lease and do not silently overwrite a
   completed peer update. Proven by
   `test_file_lexical_retriever_serializes_shared_directory_mutations`.
5. Search and stats refresh from the durable source, preserve deterministic
   score/chunk ordering, and return only bounded data; missing state is treated
   as an empty index. Proven by
   `test_file_lexical_retriever_refreshes_external_updates_and_bounds_queries`.
6. Non-JSON metadata, invalid document records, unsupported schema versions,
   invalid UTF-8, and persistence failures return typed errors or the
   documented constructor error without leaking raw paths, payloads, or
   exception details. Proven by
   `test_file_lexical_retriever_rejects_non_json_documents_without_mutation`
   and `test_file_lexical_retriever_redacts_storage_failures`.
7. The public import, API example, documentation, and existing retrieval suite
   remain green; no vector, managed-store, network, or semantic-ranking claim
   is added. Proven by the focused retrieval suite, full suite, static gates,
   and documentation smoke.

## Release and safety boundary

This is a local durable retrieval backend with at-least-once rebuild semantics:
the index is derived from the persisted documents, and a successful file write
is the authority for a mutation. It is not a distributed index, a transaction
with connector ingestion, a managed vector database, or a semantic-faithfulness
guarantee. The existing retrieval, execution-isolation, hosted-coordination,
CI-policy, and publication gates remain independent.
