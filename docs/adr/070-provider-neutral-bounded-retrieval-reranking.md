# ADR-070: Provider-Neutral Bounded Retrieval Reranking

## Status

Accepted - preview capability, local-first.

## Context

MAPLE already has bounded lexical and caller-supplied-vector retrieval with
source-bearing hits. Agent frameworks commonly add a reranking stage between
retrieval and answer generation, but the scoring model, provider, and hosting
boundary vary by deployment.

The parity ledger therefore needs a reranker extension point without adding a
model dependency, network behavior, or a claim that ranking scores measure
semantic faithfulness.

## Decision

Add a provider-neutral, host-owned `RetrievalReranker` protocol and
`rerank_hits(...)` helper:

- the host supplies `score(query, chunk)` and returns a `Result[float, Error]`;
- lexical `RetrievalHit` and vector `VectorRetrievalHit` candidates are
  accepted through one bounded helper;
- candidates are validated, chunk IDs must be unique, and the original
  retrieval score is retained beside the reranker score;
- `top_k` and candidate count are bounded, scores must be finite numbers, and
  deterministic ties use the chunk ID;
- callback exceptions, callback errors, malformed scores, and malformed
  candidates fail closed with redacted typed errors;
- MAPLE does not select a provider, make network calls, persist scores, or
  interpret the score as faithfulness or groundedness.

## Alternatives considered

1. **Add a hosted reranker dependency.** Rejected because provider credentials,
   model selection, network policy, and availability are host concerns.
2. **Replace the backend's retrieval score.** Rejected because downstream
   consumers need to compare the reranked result with the original candidate
   ranking and source contract.
3. **Accept arbitrary dictionaries from a callback.** Rejected because the
   callback boundary would lose type, source, ordering, and error guarantees.
4. **Call the reranker automatically from each backend.** Rejected because it
   would make provider execution implicit and change existing retrieval
   behavior.

## Bounds and failure modes

- The default and maximum candidate count for one call is `100` unless the
  caller supplies a smaller bound.
- Queries are non-empty and limited to `16,384` UTF-8 bytes.
- `top_k` must be between `1` and the configured candidate bound.
- Duplicate or malformed hit values return `RETRIEVAL_CANDIDATE_INVALID`.
- Callback failures return `RETRIEVAL_RERANKER_ERROR` without exception text.
- Non-finite callback scores return `RETRIEVAL_RERANKER_RESULT_INVALID`.
- The helper performs no retry, timeout, batching, persistence, or provider
  circuit-breaker operation; those remain explicit host policies.

## Consequences

Hosts can insert a reranking model or deterministic policy after either local
retrieval backend while preserving source references and the original score.
The contract closes the reranker seam in the parity ledger without pretending
that a provider-neutral score is a quality or safety judgment. Document
connectors, managed stores, provider orchestration, and semantic evaluation
remain separate follow-on capabilities.
