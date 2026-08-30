# Standard: Git Conventions

## Commits
- **Atomic:** one logical change; the tree builds and tests green at every
  commit on main.
- **Format (Conventional Commits):**
  `type(scope): imperative summary ≤72 chars`
  Types: `feat` `fix` `refactor` `test` `docs` `chore` `perf` `ci` `build`.
  Body (when the diff can't speak for itself): the why, wrapped at 72.
  Footer: `BREAKING CHANGE:` when true; issue refs (`Closes #12`).
- Read the staged diff before committing — every time. `git add -p` over
  `git add .` when the tree holds unrelated edits.
- Never mix formatting-only churn with logic in one commit.

## Branches
- `main` is always releasable. Work happens on
  `feat/<slug>` · `fix/<slug>` · `chore/<slug>` · `hotfix/<slug>`.
- Branch from fresh main; rebase (or merge main in) before review to keep
  the diff honest; delete branches after merge.
- History: squash-or-rebase small branches to readable commits before
  merge. **Never rewrite pushed/shared history.** `--force-with-lease` only
  on your own unshared branches.

## Tags & releases
- Releases are annotated tags `vX.Y.Z` on main, created deliberately by the
  human's go (they trigger publish pipelines).
- The tag's commit is exactly what shipped; no post-tag fixups — that's a
  new patch version.

## Hygiene
- `.gitignore` covers build output, caches, env files, editor droppings —
  before the first commit.
- Secrets in history = incident: rotate the secret immediately; scrubbing
  history is cleanup, not remedy.
- Lockfiles are code: committed, reviewed, never hand-edited.
- The working tree is clean at every "done" report; stashes are not storage.
