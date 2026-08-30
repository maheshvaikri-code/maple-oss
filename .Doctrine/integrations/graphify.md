---
integration: graphify
upstream: https://github.com/Graphify-Labs/graphify
package: graphifyy (PyPI)   # package is graphifyy, command is graphify
pinned_version: 0.9.12
discipline: retrieval-context-engineering
---

# graphify — Integration

`/graphify .` maps a repo (code, docs, PDFs, images, video) into a knowledge graph:
`graphify-out/graph.json` (queryable), `graph.html` (interactive), `GRAPH_REPORT.md`
(highlights). Code pass is tree-sitter AST — deterministic, fully local, zero LLM calls,
~40 languages, cross-file `calls/imports/inherits` resolution. Every edge is tagged
`EXTRACTED` (explicit in source) or `INFERRED` (resolved). Query layer:
`graphify query "<question>"`, `graphify path A B`, `graphify explain "<symbol>"`.

## Install (Claude Code primary)

```bash
uv tool install graphifyy      # or: pipx install graphifyy — avoid bare pip on Mac/Win
graphify install               # registers the skill with Claude Code (global)
graphify install --project     # repo-local registration instead
```

Gotchas worth pinning: with `uvx`, name the **package** — `uvx --from graphifyy
graphify install` (`uvx graphify` fails; the package is `graphifyy`). If `graphify:
command not found` right after install, run `uv tool update-shell` (or
`pipx ensurepath`) and open a new terminal.

## Other adapters

`graphify install --platform <codex|opencode|kilo|copilot|aider|gemini|droid|trae|
hermes|kimi|pi|claw|codebuddy>` — one flag per agent. For cross-framework discovery use
`--platform agents`, which targets the Agent-Skills spec locations (`~/.agents/skills/`
global, `./.agents/skills/` with `--project`) readable by any spec-compliant framework.

## Modes and extras

- **MCP server:** `uv tool install "graphifyy[mcp]"` → `graphify-mcp` (stdio) for
  adapters that prefer MCP over skills.
- **Git hook:** `graphify hook install` embeds the current interpreter path into a
  post-commit hook so the graph refreshes on commit — **re-run after every
  upgrade/reinstall** or the hook points at a dead interpreter.
- Extras as needed: `[pdf] [office] [video] [neo4j] [falkordb] [svg] [leiden] [ollama]
  [openai] [gemini]` — e.g. `uv tool install "graphifyy[pdf]"`.

## Doctrine wiring

- **Local-only by default.** The code pass never leaves the machine. The semantic pass
  over docs/media calls a backend only if one is configured — in FDE work this stays
  OFF (P1–P5 zero-credential guardrail); code-only graphs are the default deliverable.
- **`graphify-out/` is generated:** gitignore it; the post-commit hook rebuilds. If a
  repo wants a committed orientation doc, commit `GRAPH_REPORT.md` alone.
- **Provenance discipline:** when an agent reports structure ("X calls Y"), it carries
  the edge tag — `EXTRACTED` may be stated as fact, `INFERRED` is stated as inferred.
  Same epistemics as the parity ledger: derived claims are labeled derived.
- **RudraDB/AceIQ360 positioning note:** graphify publishes LOCOMO recall@10 0.497 and
  LongMemEval-S 76% (tied with dense RAG) at zero graph-build LLM credits — a datapoint
  for the Memory Engineering comparison table, and a validation of the
  no-embeddings-needed thesis.

## Health check

`graphify explain` on a symbol you know: expect source file + line, degree, and tagged
connections. Then `graphify path` between two modules you know are linked — a 2–4 hop
path with named edges confirms cross-file resolution is working.
