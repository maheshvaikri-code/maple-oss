---
rubric: fde-discovery
version: 0.1.0
authority: human
binds: qumba-rir
---

# FDE Discovery Rubric

Authority document for the P1 discovery interview. The model's runtime role is limited to
**question framing within the clauses below**; the validator disposes. Every proposed
question MUST cite the clause id authorizing it. Uncited or unauthorized questions are
struck without comment.

## Stages

- **S0 → S1 (Domain frame):** establish goal and primary users.
- **S1 → S2 (Ground truth):** establish data sources and the concrete demo scenario.
- **S2 → S3 (Constraints):** establish constraints and promotion target; emit spec.

## Clauses

**R1 — Question budget.** Max 3 questions per stage, max 2 rounds per stage. Budget
exhausted → mark remaining required fields `unknown-accepted` or escalate per R7.

**R2 — Question form.** Closed-choice questions preferred; at most one open question per
stage. Every question maps to exactly one unfilled field of the output schema.

**R3 — No solutioning.** During discovery the model proposes no architecture, archetype,
tool, or stack. Technology questions are prohibited before S2, and in S2 only as
constraints ("must this run in your VPC?"), never as preferences ("do you like
LangChain?").

**R4 — No leading questions.** Questions must not embed an assumed answer or steer toward
an archetype.

**R5 — Demo scenario is concrete.** S1 must produce one narratable scenario: actor, input,
action, observable output ("analyst uploads 200 PDFs, asks X, sees cited answer"). A vague
scenario ("make search better") does not satisfy this clause.

**R6 — Data reality check.** S1 must classify each data source as: available-synthetic-ok /
available-real-needed / unavailable. Any `real-needed` triggers the guardrail note in the
spec and an escalation flag.

**R7 — Escalation.** If required fields remain unresolved after budgets, emit the partial
spec with an `escalations[]` block; never pad with invented answers.

## Resolution criteria

The intent spec is resolved when every required field below is populated, or explicitly
listed in `unknowns_accepted[]` with a one-line risk note.

## Output schema — `intent-spec.json`

```json
{
  "version": "1",
  "project": "string (slug)",
  "goal": "string, one sentence",
  "primary_users": ["string"],
  "data_sources": [
    {"name": "string", "kind": "docs|db|api|events", "availability": "synthetic-ok|real-needed|unavailable"}
  ],
  "demo_scenario": {"actor": "string", "input": "string", "action": "string", "observable_output": "string"},
  "constraints": {"latency": "string|null", "privacy": "string|null", "budget": "string|null"},
  "promotion_target": "aws|gcp|azure|undecided",
  "archetype_hint": "rag-over-docs|agent-workflow|batch-eval|none",
  "unknowns_accepted": [{"field": "string", "risk": "string"}],
  "escalations": [{"reason": "string", "clause": "string"}]
}
```

Required: `project`, `goal`, `primary_users`, `data_sources`, `demo_scenario`,
`promotion_target`. Serialization follows pack-wide canonical JSON rules.

## Validator disposal checklist

1. Every question cites a clause id. 2. Budgets respected (R1). 3. Forms respected (R2).
4. No solutioning/leading (R3, R4). 5. Scenario concreteness (R5). 6. Data classification
present (R6). 7. Spec validates against the schema, or escalates per R7.
