# ADR-008: Bounded artifact and code-block boundary

**Date:** 2026-08-24
**Status:** accepted
**Deciders:** Chief Architect, Security Reviewer

## Context

Leading agent runtimes commonly exchange generated files, charts, and code
blocks as durable artifacts. MAPLE currently has bounded tool and workflow
state, but no immutable artifact identity or safe code-block extraction. A
workspace path or model-authored body is untrusted input: it must not become a
path traversal, an unbounded upload, or an implicit execution request.

This slice needs to support previews, handoffs, and later isolated execution
without claiming that storing code is the same as safely running code.

## Decision

We will add a content-addressed artifact contract and a bounded Markdown
fenced-code parser. `Artifact` records use a SHA-256 identity, byte size,
declared media type, and validated display name. `InMemoryArtifactStore` and
`FileArtifactStore` enforce per-artifact and total-store byte limits, verify
content hashes on reads, and return typed `Result` errors. `extract_code_blocks`
will parse only line-delimited triple-backtick fences, cap source and block
counts, reject unclosed fences, and return code as data; it will never execute,
interpolate, or write a block. Code and artifacts remain separate from the
future sandbox/executor boundary.

Data flow and error paths:

```text
model/user text -> bounded fence parser -> CodeBlock data
                                  \-> explicit store.put(bytes) -> hash/id
artifact id -> safe path resolver -> bounded read -> hash verification -> bytes
      malformed/oversized/path/hash failure -> Result.err, no partial artifact
```

The store owns artifact bytes and identity. Callers own authorization and may
choose whether a generated artifact is exposed to an agent or user. File
artifact paths are derived only from validated SHA-256 IDs; display names are
metadata and never filesystem paths.

## Alternatives considered

| Option | Pros | Cons | Why not |
|--------|------|------|---------|
| Immutable content-addressed stores plus explicit parser (chosen) | Deterministic identity, deduplication, bounded reads, easy handoff, no execution claim | No garbage collection or remote object-store backend yet | — |
| Temporary workspace directories | Familiar file semantics and easy subprocess integration | Path traversal/symlink cleanup risks, mutable identity, unclear retention | Too unsafe and ambiguous for the first artifact contract |
| Delegate to a hosted sandbox/artifact provider | Stronger execution isolation and remote scale | External service/auth dependency, unavailable offline, provider-specific contract | Requires a separate cloud/provider decision and human approval |
| In-memory blobs only | Smallest implementation and no filesystem attack surface | Artifacts disappear on restart and cannot support durable workflow handoffs | Retains no publishable artifact boundary |

## Consequences

- Positive: artifacts can be safely referenced by stable hash; generated code
  can be previewed or handed off without accidental execution; file-backed
  storage survives process restarts; no dependency or cloud service is added.
- Negative / debt accepted: default limits are 8 MiB per artifact, 64 MiB per
  store, 64 code blocks per document, 1 MiB source text, and 128 KiB per code
  block. There is no artifact garbage collection, remote store, signed
  provenance, or isolated execution in this slice.
- Blast radius: only callers that instantiate an artifact store write files;
  parser failures return data errors and produce no store side effect. A
  corrupt file-backed artifact is rejected rather than repaired in place.
- Invalidation triggers: a requirement for code execution, remote sharing,
  signed provenance, retention/GC, or artifact sizes above these bounds.
