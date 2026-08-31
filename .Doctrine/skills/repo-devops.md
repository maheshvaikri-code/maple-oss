# Skill: Repo DevOps

**Scope.** Repository structure, developer tooling, local environments,
hooks, and the scripts that hold a project together.

## Principles
- One-command truth: `make setup`, `make test`, `make lint`, `make build`
  (or `just` equivalents) — the same entry points locally and in CI.
- Reproducibility beats documentation: lockfiles, pinned toolchains, and
  scripts over wiki pages that rot.
- The repo teaches: a fresh clone plus the README gets a stranger to green
  tests in minutes.

## Standard repo shape
```
README.md  LICENSE  CHANGELOG.md  CLAUDE.md  .Doctrine.md  .Doctrine/
Makefile|justfile  .gitignore  .env.example
src/|<crate|pkg>/   tests/   docs/{adr,plans,reviews,qa,retro}/
.github/workflows/  scripts/
```
- Rust: `Cargo.toml` with metadata complete, `rust-toolchain.toml`,
  `Cargo.lock` committed (bins and libs alike for reproducible CI).
- Python: `pyproject.toml` as the single source (project, deps, tool
  config), `uv.lock`/lockfile committed, `src/` layout.

## Monorepo
- Use the ecosystem's native workspace (cargo workspace, uv workspace,
  pnpm workspaces — add turborepo/nx only when task graphs earn it);
  one toolchain pin and one formatter config at the root, inherited.
- CI is path-filtered: a package's pipeline runs when that package (or a
  dependency of it) changes — whole-repo builds on every commit don't scale.
- Ownership explicit: CODEOWNERS per package; cross-package changes name
  every owner in review.
- Per-package `AGENTS.md` pointers (two lines) route agents to the root
  doctrine — nested files win closest-to-file (see `04-agent-adapters.md`).
- Internal packages version together or via a changeset tool — decide
  once, in an ADR; mixed strategies rot fast.
- Splitting to a monorepo (or out of one) is a Class-L decision with an
  ADR, not a Friday refactor.

## Do
- `.env.example` documents every variable's name and shape — never values.
- Pre-commit hooks for fmt + lint + secrets scan; installing them is part
  of `make setup`.
- Scripts in `scripts/` are executable, shebanged, `set -euo pipefail`
  (bash — and note plain `sh` lacks `pipefail` and brace expansion), and
  take `--help`.
- Keep generated files out of the repo (or clearly marked and
  regenerated in CI); never hand-edit generated code or lockfiles.
- Top-level (especially dotted) directory names must be case-insensitively
  unique: `.doctrine/` silently merges into `.Doctrine/` on Windows/macOS,
  and git records paths a POSIX clone can't find.
- Commit the doctrine and CLAUDE.md — agent configuration is code.

## Don't
- Don't require undocumented global tools; declare or vendor them.
- Don't let `make test` and CI's test invocation drift apart.
- Don't gitignore the lockfile.
- Don't accumulate root-level clutter; new top-level entries need a reason.
- Don't store anything secret anywhere in the repo, including history.

## Review checklist
- [ ] Fresh-clone bootstrap verified (or documented deviation)
- [ ] Lockfiles + toolchain pins committed
- [ ] Hooks installed by setup; secrets scan among them
- [ ] Task-runner targets match CI exactly
- [ ] .env.example complete; .gitignore covers build/artifacts/env

## Common failure modes
"Works on my machine" as architecture; setup instructions in someone's
memory; CI green while local is red (or vice versa); the one sacred laptop
that can cut releases.
