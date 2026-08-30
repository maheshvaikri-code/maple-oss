---
name: doctrine-graphify
description: Doctrine shim for graphify codebase knowledge graphs. Engage whenever an agent lands in an unfamiliar or large .Doctrine repo, before any multi-file refactor or impact analysis, for questions like "how does X connect to Y", "what uses this", "where is this handled", during dead-code or god-node reviews, and at FDE P4 scaffold orientation. If you are about to grep or skim more than two files to answer a STRUCTURE question, stop — this shim routes it through the graph instead.
version: 0.1.0
requires: [graphifyy >= 0.9.12, graphify skill or MCP registered via adapter]
---

# doctrine-graphify

Query the graph instead of grepping. Grep finds strings; the graph answers structure.

## Procedure

1. **Freshness first.** If `graphify-out/graph.json` is missing or older than the last
   commit, rebuild (`/graphify .` or the post-commit hook). Never answer structure
   questions from a stale graph without saying so.
2. **Route by question shape:**
   - "what is / what touches SYMBOL" → `graphify explain "SYMBOL"`
   - "how do A and B connect" → `graphify path "A" "B"`
   - open questions ("where is auth handled") → `graphify query "<question>"`
   - orientation in a new repo → read `GRAPH_REPORT.md` (god nodes, communities,
     suggested questions) before opening any source file.
3. **Carry provenance.** Report `EXTRACTED` edges as fact, `INFERRED` edges as
   inference — the tag travels with the claim into your answer, plan, or commit
   message.
4. **Refactor gate.** Before a multi-file change, pull the target's connections
   (`explain`) and paths to its highest-degree neighbors; the blast radius goes in the
   plan. God nodes (top-degree concepts) get extra review, not casual edits.
5. **Compose with ponytail.** Ladder rung 2 ("already in this codebase?") is answered
   with one `graphify query` for the capability — reuse what the graph proves exists.

## Boundaries

Code-only, local-only by default in doctrine repos; do not configure a semantic backend
inside FDE P1–P5 (zero-credential guardrail). The graph is generated state, not source:
never hand-edit `graph.json`, never commit `graphify-out/` (a repo may commit
`GRAPH_REPORT.md` alone by charter). If tree-sitter lacks a language in the repo,
say so and fall back to reading — silently degraded coverage is worse than grep.
