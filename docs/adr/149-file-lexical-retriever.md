# ADR-149: durable local lexical retrieval boundary

**Date:** 2026-08-29
**Status:** accepted bounded local contract
**Deciders:** Chief Architect; Product Owner scope from Slice 205

## Context

`InMemoryLexicalRetriever` already validates documents, deterministically
chunks text, ranks source-bearing hits, and enforces local quotas. Connector
cursor checkpoints can survive restart, but the retrieval index itself cannot.
Persisting private term-index internals would couple the file format to an
implementation detail and make recovery harder to validate.

## Decision

Add `FileLexicalRetriever` as a local durable sibling of
`InMemoryLexicalRetriever`. The file stores only validated source documents
plus the validated chunking policy in a versioned JSON envelope. On
construction and before each public operation,
the retriever loads the envelope under a process-local reentrant lock and the
existing `DurableRecordLease`, then rebuilds a bounded in-memory lexical index
using the existing chunker. Mutations build and validate the prospective
derived index first, persist it through a temporary file with flush/fsync and
atomic replacement, and only then publish the derived state to the instance.

The file is the shared local source of truth. A missing file means an empty
index. A retriever opened with a different chunking policy rejects the existing
state instead of silently changing chunk boundaries. Malformed, oversized,
unsupported, or non-JSON state fails closed. A
successful write is durable at the file boundary, but connector ingestion,
search, and file mutation are not one transaction. Cross-process operations
are serialized by the lease; this does not claim distributed consensus or
exactly-once external effects.

## Alternatives considered

| Option | Pros | Cons | Why not |
|---|---|---|---|
| Persist validated documents and rebuild the existing lexical index (chosen) | Small stable format; deterministic recovery; reuses tested ranking and chunking; easy to audit | Rebuild cost is proportional to the bounded document set; only lexical retrieval | Meets local restart need without exposing private index internals |
| Persist chunks, term counts, and term postings directly | Faster startup and search | Larger coupled schema; duplicate validation logic; harder migrations and corruption recovery | Derived state should remain disposable and owned by the existing index |
| Use SQLite or a third-party vector/database package | Query/index durability and future scale | New storage semantics/dependency; migration, locking, and license/audit surface | Exceeds the local bounded scope and dependency policy preference |
| Keep the process-local index and only persist connector cursors | No new file format or code | Restart still loses retrieval state; concurrent local readers disagree | Does not solve the stated durability gap |

## Consequences

- Positive: local lexical RAG can be reconstructed after restart, shared local
  instances observe one durable source, and the persisted format contains no
  private ranking internals.
- Negative / debt accepted: every operation may rebuild up to the configured
  document/chunk bounds; writes are atomic but not transactional with a
  connector or embedding provider; vector persistence remains separate.
- Security: JSON parsing is size-bounded and validated before publication;
  file writes use a same-directory temporary file, fsync, atomic replace, and
  a durable record lease; no network, pickle, eval, subprocess, or raw storage
  exception is exposed.
- Thread safety: one `FileLexicalRetriever` serializes operations with its
  instance lock; multiple instances coordinate through the file lease. Search
  results are detached dataclass values from the rebuilt index.

## Invalidation triggers

A need for vector persistence, managed stores, multi-host replication,
connector/index atomic transactions, high-volume query latency, automatic
compaction, or semantic ranking reopens this ADR and its file-format decision.
