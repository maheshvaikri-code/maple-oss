# ADR-022: Deterministic grounded-answer evaluation

**Date:** 2026-08-24  · **Status:** accepted  · **Deciders:** Chief Architect

## Context

MAPLE now evaluates retrieval source coverage, but it does not yet provide a
local check for whether a generated answer's bounded claims are supported by
the retrieved source text. A semantic judge would add model, cost, privacy,
and reproducibility concerns that are not required for the first native
contract.

## Decision

We will add a dependency-free `EvaluationHarness.run_groundedness` contract.
Each bounded case supplies a query and source URI/text pairs. A runner returns
a bounded answer observation. MAPLE splits the answer into claims and scores a
claim as supported when its normalized non-stopword token overlap with at least
one source meets the case threshold. The report exposes supported/unsupported
claim counts, ratios, and source URIs without treating lexical overlap as
semantic entailment or an LLM-as-judge result.

- Case and source text are JSON-safe and byte-bounded; source URIs are unique
  and validated.
- Answers are bounded, non-empty text; claims are deterministic and capped.
- Runner failures, malformed observations, and threshold failures remain
  per-case typed errors and do not abort the remaining cases.
- The metric is an evaluation proxy only. It must not be described as proof of
  factuality, citation entailment, or semantic faithfulness.

## Alternatives considered

| Option | Pros | Cons | Why not |
|---|---|---|---|
| Bounded lexical claim-support proxy (chosen) | Dependency-free, deterministic, local, inspectable | Misses paraphrase and semantic contradiction | Best first contract with an honest narrow claim |
| LLM-as-judge faithfulness | Can assess paraphrase and nuanced support | Model drift, cost, privacy, prompt injection, and nondeterminism | Requires a separate provider/governance contract |
| Exact answer/source string matching | Very simple and reproducible | Rejects valid paraphrases and does not measure claims | Too brittle for generated text |

## Consequences

- Positive: retrieval evaluation can be paired with a reproducible bounded
  groundedness signal before release or regression testing.
- Negative / debt accepted: lexical overlap is not semantic entailment and can
  miss paraphrases or accept shallow word overlap; multilingual quality is
  limited by the tokenizer and stopword set.
- Invalidation triggers: a semantic evaluator contract, calibrated multilingual
  metrics, claim extraction from structured model output, or trusted citation
  entailment would require a new ADR and review.
