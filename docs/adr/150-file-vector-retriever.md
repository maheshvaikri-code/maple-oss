# ADR-150: Durable local vector retrieval

**Status:** Accepted for Slice 206 implementation
**Date:** 2026-08-29
**Decision owners:** Chief Architect / Backend / Security / QA / Release

## Context

MAPLE's `InMemoryVectorRetriever` already validates caller-supplied vectors,
enforces a single index dimension, chunks source-bearing documents, and
returns deterministic cosine-similarity hits. Its state is process-local,
however. The preceding slice added `FileLexicalRetriever`, so local hosts can
persist lexical documents but still lose vector state on restart. A durable
vector surface is useful for local RAG parity, provided it does not masquerade
as a managed database, embedding service, or distributed consistency layer.

## Decision

Add a public `FileVectorRetriever` with a versioned, bounded JSON file as its
local source of truth. The envelope stores:

- the validated `TextChunker` policy;
- each validated source `Document`; and
- one validated finite vector for every generated document chunk.

On construction and before every operation, MAPLE reads the bounded file and
rebuilds an `InMemoryVectorRetriever`. Add and remove operations validate a
candidate index first, then persist it with a same-directory temporary file,
flush, `fsync`, and atomic replacement. An existing `DurableRecordLease` and
the instance lock serialize local cross-process and same-process mutations.

The persisted dimension is derived by rebuilding the candidate rather than
being trusted as an independent field. Empty documents are valid and persist
with an empty vector list; they contribute no dimension. All non-empty vector
records must agree on one dimension through the existing in-memory contract.

Errors at the file boundary are typed and generic. Constructor load failures
are surfaced as the documented `ValueError`, while operation failures return
redacted `Result` errors. Raw paths, payloads, and exception text do not cross
the boundary.

## Alternatives considered

1. **Persist source documents and vectors, rebuild the in-memory index — chosen.**
   It reuses the tested chunking, vector validation, scoring, limits, and hit
   contract; the file remains inspectable and dependency-free; restart cost is
   bounded by configured quotas.
2. **Persist derived chunks and vector lookup records.** Reopening could be
   faster, but it duplicates chunker invariants and creates two sources of
   truth that can drift when chunking behavior changes.
3. **Use SQLite or a vector database dependency.** This could support larger
   indexes and richer queries, but adds dependency, migration, operational,
   and security scope that is not required for a local parity increment.
4. **Leave vector persistence deferred.** This keeps the surface smaller but
   leaves local RAG durability asymmetrical and makes already-produced
   embeddings needlessly ephemeral.

## Threat sketch and controls

| Threat | Control |
| --- | --- |
| Unbounded state or query resource use | Byte, document, vector, dimension, result, and chunker limits; bounded reads use `max_bytes + 1`. |
| Corrupt or hand-edited state | Version, policy, document, vector, count, finite-value, and dimension validation; fail closed before mutation. |
| Torn or partial writes | Same-directory temporary file, flush, `fsync`, and atomic replacement. |
| Lost concurrent local update | `DurableRecordLease` around load/validate/write plus per-instance `RLock`; each mutation reloads current state. |
| Metadata or storage error disclosure | JSON validation and generic typed errors; raw exception details and paths are not returned. |
| False hosted/distributed capability claim | Public docs explicitly scope this to local caller-supplied embeddings and exclude managed/distributed behavior. |

## Consequences

Positive consequences:

- local vector retrieval survives process restart;
- independent local instances refresh the same durable source of truth;
- no new runtime dependency or provider/network behavior is introduced; and
- the vector and lexical durable surfaces share predictable local safety
  properties.

Tradeoffs:

- JSON rebuilds are bounded but not an optimized large-scale vector index;
- callers must generate and supply embeddings;
- the file is a local durability boundary, not a distributed transaction; and
- changing the chunking policy requires a new compatible directory or an
  explicit migration decision.

## Rollback

Rollback is additive and reversible: remove the new public export and
`FileVectorRetriever` implementation plus its tests/docs, leaving the prior
`InMemoryVectorRetriever` and `FileLexicalRetriever` contracts unchanged. Do
not delete a user's state file as part of rollback; preserve it for inspection
and an explicit migration decision.

## Verification

The slice brief maps each acceptance criterion to focused regression tests.
The release gate also requires the full suite, Black, Ruff, mypy,
`compileall`, project-scoped `pip-audit`, and a clean archived package smoke.
