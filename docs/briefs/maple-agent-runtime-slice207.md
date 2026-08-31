# Slice 207 brief - bounded retrieval and citation tool

**Date:** 2026-08-29
**Class:** L (new public agent-tool factory and cross-layer retrieval contract)
**Roles:** Product Owner / Chief Architect / Backend / Security / QA / Release

## Problem

MAPLE already provides bounded lexical and vector retrieval backends that
return source-bearing hits, but an autonomous agent cannot invoke a lexical
backend through the normal `ToolRegistry` loop without writing a host-specific
wrapper. This leaves the retrieval/RAG parity surface below the tool and
citation ergonomics exposed by the comparison frameworks.

## Scope

- In: a public `create_retrieval_tool()` factory over the existing lexical
  `RetrievalBackend` contract; bounded query and result-count parameters;
  deterministic JSON-safe hit/citation serialization; output byte bounds;
  generic backend and malformed-hit errors; read-only tool metadata and tags;
  public exports; focused regressions; API/README/parity/changelog and release
  bookkeeping.
- Out: embedding generation or vector-query orchestration, network fetching,
  connector ingestion, managed stores, reranking, source metadata passthrough,
  retrieved-content execution, prompt injection filtering claims, remote
  transport, and distributed coordination.
- Deferred: a vector retrieval tool requires a separate explicit contract for
  host-owned query embedding and provider/model errors.

## Constraints and assumptions

- The factory accepts an object exposing the existing `search(query, top_k=)`
  lexical retrieval method. The backend remains the authority for indexing and
  scoring; the tool only adapts its bounded result into model-visible data.
- The model may choose `top_k` only within the factory's configured finite
  bound. Query text is bounded by UTF-8 bytes, not only Python characters.
- Each returned hit must be a validated `RetrievalHit` with a finite score,
  bounded identifiers, source URI, optional title, bounded text, and string
  matched terms. Source and chunk metadata are deliberately omitted from the
  model result by default to reduce accidental data disclosure.
- The serialized result is checked as one UTF-8 JSON value against a finite
  byte bound. Oversized output fails closed; it is not silently truncated.
- Backend exceptions and malformed `Result` values become generic typed tool
  errors. Raw exception text, paths, and backend payloads do not cross the
  public tool boundary.
- The tool is read-only and does not require approval by default. A host may
  wrap or replace the returned `Tool` if its local policy requires approval.

## Acceptance criteria

1. Valid factory configuration returns a `Tool` with a bounded `query` and
   `top_k` schema, retrieval tags, read-only defaults, and a description that
   states the source-bearing result contract. Invalid retriever, name, bounds,
   or output-size configuration fails fast.
2. A valid lexical backend result is adapted into deterministic JSON-safe
   `hits` containing chunk/document IDs, text, finite score, matched terms,
   and source URI/title while excluding source and chunk metadata. The result
   schema is enforced through normal `Tool.execute()` validation.
3. Empty/control/oversized queries, invalid top-k values, oversized serialized
   results, malformed hits, duplicate chunk IDs, non-finite scores, and
   non-JSON-safe values fail before a partial result is returned.
4. Backend exceptions, non-`Result` returns, and backend error payloads are
   normalized to bounded generic errors without leaking private exception text,
   paths, or payload contents.
5. The public factory is importable from `maple.autonomy` and `maple`, and the
   API reference, README, parity ledger, changelog, and release plan describe
   the exact read-only lexical/citation boundary. No vector, network,
   execution, managed-store, or hosted capability claim is added.
6. Focused retrieval/tool regressions, the full suite, static gates,
   project-scoped dependency audit, and clean package smoke remain green.

## Release and safety boundary

This is a local adapter that makes an existing retrieval backend usable from a
model tool loop. It does not prove source truth, semantic faithfulness,
citation correctness, prompt-injection resistance, or authorization to access
the backend's corpus. Hosts remain responsible for corpus policy, source
access, redaction, and any approval decision. Existing CI-policy, execution
isolation, hosted-coordination, dependency, and publication gates remain
independent.
