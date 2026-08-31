# Skill: ML Engineering

**Scope.** AI/ML-powered features — LLM applications, RAG systems, and
classical models — from prompt to production, evals included.

## Principles
- Evals are the tests of AI. No prompt, model, or retrieval change ships
  without before/after numbers on a versioned golden set — the ML form of
  "behavior changes ship with tests."
- Prompts are code: versioned, reviewed, diffed. A prompt edited live in a
  console is an untracked production change.
- Model IDs and parameters are pinned dependencies (see
  `standards/dependency-policy.md`); an upgrade is a migration landed with
  eval evidence, not a string swap.
- Non-determinism is handled deliberately, never shrugged at: temperature 0
  and seeds where the provider supports them; property-style assertions
  (schema holds, facts present, length bounded) over exact-match where not.
- An AI feature without a fallback is an outage with extra steps. Decide
  what happens when the model is down, slow, or wrong — before launch.

## Defaults
- Golden set: versioned in the repo, labeled, covering happy paths, edge
  cases, and known failures; grown from production misses, never shrunk to
  make a change look good.
- LLM-as-judge only after calibrating the judge against human labels on a
  sample; report agreement, and re-check when the judge's model changes.
- RAG: retrieval measured separately from generation — recall@k on labeled
  queries for the retriever, groundedness checks on the generator. Chunk
  size and overlap are tunables with eval evidence, not guesses.
- Budgets per feature: tokens, cost, and latency, with alerts wired per
  `skills/observability.md`.

## Do
- Log traces — prompt version, retrieved-context refs, output, token
  counts — with PII stripped, so failures are debuggable after the fact.
- Validate model output against a schema at the boundary; treat parse
  failure as a handled error path with a retry-or-fallback decision.
- Treat retrieved documents and user content as untrusted input: handle
  them injection-aware, never as instructions to obey.
- Clear customer data flows to any model or vendor through
  `skills/privacy-compliance.md` before the first request, not after.

## Don't
- Don't ship a "small prompt tweak" without eval numbers — small tweaks
  have large blast radii.
- Don't eval on the examples the prompt was tuned against and call it
  held out.
- Don't present judge scores or offline metrics as verified user outcomes —
  say what was measured (the doctrine's honesty rules apply to numbers).
- Don't let `latest` model aliases float in production.
- Don't hardwire a vendor SDK through the codebase; keep the model call
  behind one seam so fallback and migration stay possible.

## Review checklist
- [ ] Before/after eval numbers on the versioned golden set, in the PR
- [ ] Prompt changes reviewed as diffs; model ID + parameters pinned
- [ ] Output schema validated; untrusted text handled injection-aware
- [ ] Fallback behavior defined and tested for model down/slow/degraded
- [ ] Token/cost/latency budgets set with alerts; traces logged minus PII
- [ ] Customer data flows cleared via `skills/privacy-compliance.md`

## Common failure modes
Prompt tuned live until the demo works, with no record of what changed;
golden set quietly pruned of the cases the new prompt fails; a judge model
grading its own homework uncalibrated; RAG blamed on the generator when
recall@k was never measured; a floating model alias upgrading production
over a weekend.
