# .Doctrine/ — The Company Behind the Code

This folder turns Claude Code into a full software company for this
repository: thirty roles (nineteen engineering + seven startup-profile
founder-ops + four governance heads), forty skill playbooks, eight
standards plus six language profiles, a gated workflow, integrations, a
state plane, and templates for every artifact the workflow produces.

## Layout

```
.Doctrine.md            Root operating system (always loaded via CLAUDE.md import)
.Doctrine/
├── 00-charter.md       Values and operating principles
├── 01-workflow.md      Lifecycle, gates G0–G7, task classes, loops
├── 02-role-protocol.md How roles are adopted, switched, and arbitrated
├── 03-parallel-execution.md  Subagent fan-out: workers, verifiers, reconcile
├── 04-agent-adapters.md      Run the doctrine on Codex/Cursor/Windsurf/Copilot/any agent
├── 05-packaging.md     Distribution: installer, Claude Code plugin, MCP server, wheel
├── adapters/           Ignition files: AGENTS.md (universal) + per-tool overlays
├── roles/              30 role cards (19 engineering incl. FDE, SRE, data/ML,
│                       compliance + 7 startup founder-ops (draft-never-send)
│                       + 4 governance heads: head-of-ai, head-of-data,
│                       ciso, risk-officer — policy above the gates)
├── skills/             40 discipline playbooks (G0 requirements → G1
│                       architecture → full SDLC: backend→mobile, ML, data,
│                       incident response, privacy, i18n, a11y, IaC, metrics…
│                       + startup craft: marketing→fundraising)
├── standards/          8 hard standards (incl. enterprise merge/promotion
│                       + GRC governance) + languages/ profiles
├── templates/          9 artifact templates (brief, ADR, plan, reviews,
│                       merge verdict, release, retro, risk register)
├── integrations/       Third-party tool wiring: FDE/floci overview, ponytail, graphify
├── rubrics/            Authority documents for interview-style gates (FDE discovery)
├── schemas/            JSON Schemas for machine-checked artifacts (parity ledger)
├── examples/           Worked examples (floci.manifest.yaml)
└── state-plane/        Session statefulness: checkpoint protocol, distillates, hydration
.claude/agents/         14 ready subagents (8 parallel workers, 6 fresh-context verifiers)
```

## Install (per project)

1. Copy `.Doctrine.md`, `.Doctrine/`, and `.claude/agents/` into the repo root.
2. Add `@.Doctrine.md` to the project `CLAUDE.md`.
3. Commit both. The doctrine is part of the codebase.

## Design principles

- **Progressive disclosure.** Only the root file loads at startup; everything
  else is read on demand via the routing table. Keeps context lean.
- **Closed loops.** Every gate failure routes back to the gate that owns the
  defect; every incident feeds a retrospective; retros amend the doctrine.
- **Honesty over optimism.** The doctrine's single most enforced rule is that
  reported status must match executed reality.
- **Right-sized ceremony.** Task classes (S/M/L/HOTFIX) prevent a typo fix
  from triggering a seven-gate parade.

## Customizing

Edit anything. Repo-specific overrides belong in the project `CLAUDE.md`
(more specific instructions win). Cross-project improvements belong here,
proposed through a G7 retrospective.
