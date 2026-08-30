---
spec: doctrine-hydration
version: 0.1.0
---

# HYDRATION.md — the rehydration compiler

Input: repo at HEAD + the state plane. Output: one bounded, deterministic bundle —
`.doctrine-state/local/hydration.bundle.ison` (canonical) and `.md` (human/adapter
fallback). The bundle is generated state: it lives in `local/`, never committed.

## Assembly order and token budget

Priority order — earlier sections are never trimmed. Budgets are measured **post-ISON**
(the ~68.6% reduction is why the whole plane fits in a corner of the window). Default
total: 6,000 tokens; per-adapter override in the repo charter.

| # | Section | Source | Budget | Degrade-to on overflow |
|---|---|--:|--:|---|
| 1 | Repo + role charter invariants | REPO.md, ROLE.md (invariant blocks only) | 800 | never trimmed |
| 2 | Control block | checkpoint.json | 200 | never trimmed |
| 3 | Active intents | intent/ scoped to session target | 1,200 | titles + acceptance criteria only |
| 4 | Distillate | latest, + dead_ends merged from last K | 1,600 | dead_ends + open_threads only |
| 5 | Decisions slice | entries tagged to active intents only | 800 | decision ids + one-line titles |
| 6 | Graph slice | `graphify explain` on intent-named symbols | 1,000 | god nodes + EXTRACTED edges only |
| 7 | Unresolved effects | effects/ where status != confirmed | 400 | count + most-recent entry |

Every trim is recorded in the bundle header (`trimmed: [section...]`) — the agent knows
what it doesn't know. The whole decision log, full graph, and transcript are NEVER
bundle candidates; they are query targets, not context.

## Bundle header

`{at_commit, checkpoint_seq, bundle_sha256, generated_at, trimmed[], stale[]}`.
Any source artifact behind HEAD enters content prefixed `STALE@<commit>` and is listed
in `stale[]`; a stale graph triggers rebuild-first when the graphify hook is installed.

## Determinism gate

`hydrate --check` compiles twice against the same HEAD + state plane and asserts
identical `bundle_sha256` (timestamp fields excluded from the hashed body, carried in
the header only). CI-able. Cross-time: diffing bundle bodies between checkpoints is a
ReplayLens-style drift report on the state plane itself — what changed in what the
agent is told, commit over commit.

## CLI surface

`doctrine state hydrate [--check|--if-present|--emit-agents]` · `checkpoint` ·
`verify` · `prune` · `status`. **Implemented**: `tools/doctrine_state.py` —
stdlib-only Python, zero deps, canonical JSON writer shared with the
sibling packs. (`hydrate` verifies the chain first and refuses to compile
from tampered state; the AGENTS.md emit block is timestamp-free so
unchanged state emits byte-identical files.)

## Adapter emit

The bundle is plain text, so statefulness becomes an emit target like everything else:

- **Claude Code:** SessionStart hook runs `doctrine state hydrate`; `CLAUDE.md` carries
  one line — `@.doctrine-state/local/hydration.bundle.md`. A `/checkpoint` command file
  wraps the checkpoint protocol; optional Stop hook auto-checkpoints session end.
  (Same lifecycle-hook pattern ponytail already proved out.)
- **Codex:** hydrate via lifecycle hook; bundle referenced from `AGENTS.md`;
  `/checkpoint` as a plugin command.
- **Cursor:** `.cursor/rules/doctrine-state.mdc` with `alwaysApply`, body = bundle
  include; hydrate runs from a pre-session task or git hook.
- **Windsurf:** `.windsurf/rules/doctrine-state.md`, same pattern.
- **Copilot CLI:** bundle section injected into `copilot-instructions.md` at hydrate.
- **Generic / AGENTS.md readers:** hydrate writes a fenced `<!-- doctrine:state -->`
  block into `AGENTS.md` between markers; anything that reads AGENTS.md is stateful
  with zero further integration.

One rule across all targets: adapters embed the bundle **by reference or marker-managed
block**, never by hand-pasting — the compiler owns the content, the adapter owns the
location.
