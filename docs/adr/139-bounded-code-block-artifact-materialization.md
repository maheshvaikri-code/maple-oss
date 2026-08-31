# ADR-139: Bounded code-block artifact materialization

**Date:** 2026-08-29
**Status:** accepted
**Deciders:** Chief Architect

## Context

MAPLE can extract bounded Markdown fences as `CodeBlock` data and can store
arbitrary bounded bytes in content-addressed `ArtifactStore` implementations.
Callers currently have to repeat the encoding and naming bridge themselves,
which makes block provenance and byte-preservation conventions easy to drift.
The bridge must remain a data operation and must not create an execution path.

## Decision

We will add `CodeBlock.sha256` and an additive
`materialize_code_block(store, block, *, name=None)` helper. The helper will
validate the block and store contract, encode the code as UTF-8, use a bounded
deterministic `code-block-{index}.{language}` name by default, and delegate the
bytes to the existing `ArtifactStore.put(..., media_type="text/plain")` path.
The returned artifact ID is therefore the hash of the exact stored bytes.
Store failures are returned as typed errors; no execution, parsing, network
fetch, or automatic cleanup is performed by this bridge.

## Alternatives considered

| Option | Pros | Cons | Why not |
|--------|------|------|---------|
| Add a small materialization helper over `ArtifactStore` (chosen) | Reuses existing quota/hash/persistence boundaries; additive; easy to remove; preserves exact bytes | Does not provide execution or remote distribution | Fits the current local data contract and keeps the trust boundary explicit |
| Add `CodeBlock.to_file()` | Familiar for callers; simple local output | Bypasses artifact quotas, content addressing, and file-store policy | Rejected: creates a second persistence path |
| Add a sandbox/execution-backed artifact pipeline | Could run code and capture outputs | Requires isolation, approval, cleanup, dependency, and side-effect contracts | Rejected: separate security project, not an extraction/storage bridge |

## Consequences

- Positive: one tested path preserves code bytes and derives stable artifact
  identity while retaining language/index context in metadata.
- Negative / debt accepted: artifact names are descriptive metadata, not a
  security authority; execution and remote provenance remain host-owned.
- Invalidation triggers: reopen this decision when a reviewed sandbox,
  artifact provenance/attestation, or remote artifact-transfer contract is
  approved.
