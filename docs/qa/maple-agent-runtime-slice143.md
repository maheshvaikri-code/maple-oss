# MAPLE Agent Runtime Slice 143 QA Record

Date: 2026-08-28

## Scope

This record covers native asynchronous completion for the built-in
OpenAI-compatible and Anthropic providers. The implementation awaits an
optional native async SDK client and retains the base provider's explicit
synchronous compatibility fallback when that client is unavailable.

## Functional evidence

- Focused provider/content regression: `46 passed in 0.41s`.
- Exact tracked test manifest (`git ls-files tests`): `1389 passed, 1 skipped
  in 230.95s`.
- New offline fixtures verify both adapters await their async client, preserve
  message formatting and stop controls, and parse the normal response.

## Static and boundary evidence

- `python -m mypy maple --follow-imports=skip --ignore-missing-imports`:
  `Success: no issues found in 97 source files`.
- Changed-surface Black: `3 files would be left unchanged`.
- Changed-surface isort: passed.
- Changed-surface Ruff: `All checks passed!`.
- `python -m compileall -q maple tests`: passed.
- `git diff --check b946496..HEAD`: passed.
- Committed-tree high-confidence secret scan: `committed_tree_secret_matches=0`.
- Committed-tree dangerous-construct scan:
  `committed_tree_dangerous_construct_matches=0`.

The broader working-tree Black/isort checks still report pre-existing
formatting debt in untouched legacy tests. User-owned untracked Doctrine
fixtures are not part of the committed archive and were not modified.

## Package evidence

A clean `git archive HEAD` snapshot built successfully as `maple-oss-1.1.3`:

- wheel: `104` archive entries;
- sdist: `612` archive entries;
- `twine check`: both artifacts passed;
- `pip install --no-deps --target ...`: passed;
- isolated import smoke for `ChatMessage`, `ImageContent`, `Principal`,
  `OpenAIProvider`, and `AnthropicProvider`: passed.

The clean archive excludes the workspace-only Doctrine files, local tools,
website mirror, and preserved user edits.

## Security disposition

The environment-wide `pip-audit` gate remains a release veto, unchanged by
this slice: `384 known vulnerabilities in 77 packages`, with additional
locally installed packages that could not be audited from PyPI. No dependency
was added by this slice. No publication, deployment, cloud action, or website
update was performed.

## QA decision

The slice is functionally ready and package-boundary verified. It is not a
clean publish candidate until dependency governance and the repository's
independent-review requirements are resolved.
