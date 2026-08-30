# doctrine-integrations: ponytail + graphify

Wires two third-party OSS tools into `.Doctrine` as **integrations** — thin shims over
pinned upstream, never vendored copies. Both are actively developed; vendoring would go
stale and fork the behavior silently.

## Installed layout (merged into `.Doctrine/` at doctrine v0.1.3)

```
.Doctrine/
├── integrations/
│   ├── README.md            ← you are here (index; also see fde.md)
│   ├── ponytail.md          ← pin, per-adapter install, health check, precedence
│   └── graphify.md          ← pin, install, modes, doctrine wiring
└── skills/
    ├── ponytail.md          ← doctrine-side shim: when agents engage it
    └── graphify.md          ← doctrine-side shim: graph before grep
```

The shim skills are routed via `.Doctrine.md` §6; the `integrations/*.md` files are
for humans (and for agents running setup/health tasks).

## What each one is

**ponytail** (`DietrichGebert/ponytail`, MIT, pinned v4.8.4) — a behavioral skill that
forces the laziest solution that works via a 7-rung ladder (YAGNI → reuse → stdlib →
native platform → installed dep → one line → minimum that works), with validation,
security, data-loss handling, and accessibility explicitly never on the chopping block.
Benchmarked at ~54% less code, ~20% cheaper, ~27% faster on real Claude Code sessions.

**graphify** (`Graphify-Labs/graphify`, pinned PyPI `graphifyy` 0.9.12) — `/graphify .`
maps a repo into a queryable knowledge graph (`graph.json` + `graph.html` +
`GRAPH_REPORT.md`). Code pass is tree-sitter AST: deterministic, local, zero LLM calls,
~40 languages. Every edge is tagged `EXTRACTED` (explicit in source) or `INFERRED`
(resolved), and `graphify query|path|explain` replaces grepping for structure questions.

## Taxonomy placement

ponytail → **Behavior Engineering** (sits beside OpenGuide/GuidanceGrid: GuidanceGrid
governs general behavioral conformance; ponytail governs code-brevity behavior
specifically). graphify → **Retrieval/Context Engineering** (deterministic code-structure
retrieval; complements RudraDB/ContextChain rather than overlapping — no embeddings, no
vector store). Note for AceIQ360 positioning: graphify publishes LongMemEval-S 76% and
LOCOMO recall figures — worth a line in your Memory Engineering comparison table.

## Precedence (binding, in order)

1. **Repo charter invariants beat the ladder.** Determinism scaffolding — canonical
   JSON, hash gates, conformance vectors, seeded PRNGs — counts as validation/safety
   and is never simplified away, even under `ultra`.
2. **Rung 5 is charter-constrained.** Ponytail's "already-installed dependency? use it"
   yields to a repo pinned stdlib-only/zero-dependency (most of your OSS libraries):
   in those repos rung 5 is skipped and the ladder goes 4 → 6.
3. **Graph before grep.** When a fresh `graph.json` exists, structure questions route
   through graphify queries; ponytail's rung 2 ("already in this codebase?") is answered
   by `graphify explain/query`, not by skimming.

## Composition

The two reinforce each other: graphify makes rung 2 cheap and precise (reuse what exists,
found in one query), and ponytail keeps the graph small (less code → fewer nodes). In the
FDE pipeline: run P4 builds under `ponytail full` (prototypes must stay minimal), and
optionally ship `GRAPH_REPORT.md` in the deliverable as the handoff orientation doc.
