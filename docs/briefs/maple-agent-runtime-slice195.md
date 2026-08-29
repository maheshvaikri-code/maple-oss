# Slice 195 brief - bounded code-block artifact materialization

**Date:** 2026-08-29
**Class:** L
**Role:** Chief Architect / Backend / Security / QA / Release
**Status:** proposed

## Objective

Make extracted Markdown code blocks first-class immutable artifacts without
crossing into code execution. A caller should be able to preserve the exact
UTF-8 source bytes, language, and block position through the existing bounded
artifact store and receive a content-addressed identity.

## In scope

- a stable SHA-256 digest view for a validated `CodeBlock`;
- `materialize_code_block()` over the existing `ArtifactStore` protocol;
- deterministic safe default artifact names derived from bounded block metadata;
- exact byte preservation for in-memory and file-backed stores;
- typed validation and store-error handling, exports, tests, and public docs.

## Out of scope

- parsing beyond the existing fenced-block extractor;
- code execution, evaluation, compilation, subprocesses, sandboxes, browser or
  computer use, network fetches, or hosted artifact services;
- artifact deletion, retention policy, provenance attestation, or remote
  distribution;
- new dependencies, cloud, publication, or website changes.

## Acceptance criteria

1. A valid block materializes to an artifact whose bytes exactly equal the
   block's UTF-8 code and whose ID is the SHA-256 of those bytes.
2. The default artifact name is deterministic, bounded, and carries the block
   index and validated language without path traversal characters.
3. In-memory and file-backed stores expose identical materialization behavior;
   file-backed artifacts remain readable after recreation.
4. Invalid blocks, oversized code, invalid stores, and store failures return
   typed errors without executing code or partially mutating the caller's
   artifact store.
5. The helper is publicly exported and documented with one runnable example;
   documentation explicitly keeps execution and sandboxing outside the
   contract.
