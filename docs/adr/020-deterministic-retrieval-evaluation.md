# ADR-020: Deterministic retrieval and citation evaluation

**Date:** 2026-08-24  · **Status:** accepted  · **Deciders:** ML Engineer

## Context

MAPLE has bounded lexical and caller-supplied-vector retrieval with stable
source references, but its evaluation harness only checks generic outputs and
tool trajectories. Hosts need a deterministic recall/precision gate for
retrieval quality before judging generated answers. A first slice must remain
dependency-free and must not imply that source overlap proves answer
faithfulness.

## Decision

Add `RetrievalEvalCase` and `EvaluationHarness.run_retrieval`.

- Cases declare a bounded query, a non-empty golden set of expected source
  URIs, and minimum precision/recall thresholds.
- The runner may return lexical `RetrievalHit` or vector
  `VectorRetrievalHit` values, directly or through MAPLE's `Result` boundary.
- Evaluation deduplicates source URIs, computes source-level precision,
  recall, and F1, and returns a bounded `EvalReport` with redacted metrics.
- Malformed observations, runner errors, exceptions, oversized cases, and
  invalid thresholds become typed per-case or top-level failures; one bad
  case does not abort the remaining valid cases.
- This slice measures retrieval/source coverage only. It does not evaluate
  answer relevance, groundedness, entailment, citation placement, or an
  LLM-as-judge. Those require a separately calibrated generation-evaluation
  contract and pinned model evidence.

## Alternatives considered

| Option | Pros | Cons | Why not |
|---|---|---|---|
| Deterministic source precision/recall (chosen) | Fast, reproducible, no model or vector dependency | Does not prove generated-answer faithfulness | Establishes the retrieval gate first and reports its exact scope |
| LLM-as-judge now | Covers semantic answer quality | Model drift, cost, calibration, and untrusted judge output | Requires a pinned/calibrated judge and human-labeled agreement set |
| Generic `EvalCase` only | No new API | Hosts duplicate hit parsing and metric logic | Loses a shared source-level contract and consistent bounds |

## Consequences

- Positive: lexical and vector retrievers share one offline quality gate with
  explicit source-level metrics and deterministic ties inherited from the
  retrieval layer.
- Negative / debt accepted: no generation faithfulness or citation-entailment
  score is claimed; expected URI golden sets are host-maintained.
- Invalidation triggers: reopen when answer-generation evaluation, citation
  span validation, calibrated judge models, or dataset versioning are added.
