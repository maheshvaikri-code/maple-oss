---
integration: ponytail
upstream: https://github.com/DietrichGebert/ponytail
license: MIT
pinned_version: 4.8.4
discipline: behavior-engineering
---

# ponytail — Integration

Behavioral layer: the agent stops at the first ladder rung that holds instead of
over-building. Modes: `lite | full (default) | ultra`, switched with `/ponytail <mode>`,
disabled only by "stop ponytail" / "normal mode". Ships six skills — `ponytail` (core
ladder), `ponytail-review`, `ponytail-audit`, `ponytail-debt`, `ponytail-gain`,
`ponytail-help` — plus slash commands and two Node.js lifecycle hooks.

## Install per adapter

- **Claude Code:** `/plugin marketplace add DietrichGebert/ponytail` then
  `/plugin install ponytail@ponytail`. Requires `node` on the non-interactive PATH for
  the always-on hooks; without it the skills still work, activation just stays quiet.
- **Codex:** `codex plugin marketplace add DietrichGebert/ponytail` then
  `codex plugin add ponytail@ponytail`; open `/hooks`, review and trust the two
  lifecycle hooks, start a new thread.
- **Copilot CLI:** `copilot plugin marketplace add DietrichGebert/ponytail` then
  `copilot plugin install ponytail@ponytail`.
- **OpenCode:** add `{ "plugin": ["./.opencode/plugins/ponytail.mjs"] }` to
  `opencode.json` (path resolves against the project; use an absolute path to share one
  checkout). OpenCode also auto-loads the repo's `AGENTS.md` as fallback.
- **Qoder / CodeWhale / Swival and other AGENTS.md readers:** zero setup from a
  checkout, or copy `AGENTS.md` into the project root (instruction-only fallback —
  rules hold, no mode switching).
- **Gemini CLI / Antigravity:** via `gemini-extension.json`; Antigravity converts the
  commands into chat-typed skills.

Cursor/Windsurf adapters: use the `AGENTS.md` fallback until upstream ships native
plugins; track upstream releases before bumping `pinned_version`.

## Health canary

After install, ask the agent for "a date picker for this form." Pass: it emits
`<input type="date">` (or the platform-native equivalent) with a one-line rationale.
Fail: it reaches for a picker library — hooks aren't loading; check `node` on PATH and
re-run the plugin install.

## Precedence in .Doctrine (binding)

1. Determinism scaffolding (canonical JSON, hash gates, conformance vectors, seeded
   PRNGs) is classed with ponytail's own never-cut list (validation, security,
   data-loss, a11y). No mode may simplify it away.
2. In repos chartered stdlib-only/zero-dependency, rung 5 (use an installed dep) is
   struck; ladder runs 1-2-3-4-6-7.
3. Mode defaults by context: `full` everywhere; `ultra` permitted for FDE P4 prototype
   scaffolds and demos; never `ultra` on library/public-API code where explicitness is
   part of the contract.

## Upgrade path

Bump `pinned_version` only after re-running the health canary and re-reading the diff of
`skills/ponytail/SKILL.md` upstream — the ladder wording is the behavioral contract.
