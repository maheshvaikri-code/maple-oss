# Language Profile: Python

**Applies when.** Any Python package, script, or PyO3 host in the repo.

## Toolchain
- Target modern supported minors, declared in `pyproject.toml` (single
  source for project, deps, and tool config). `uv` for envs and locking;
  lockfile committed; `src/` layout.

## Format & lint
- `ruff` for lint **and** format, checked in CI.

## Types & idioms
- Type hints required on all public functions and encouraged everywhere;
  `pyright` (or mypy strict) clean on new/changed code; legacy debt
  tracked, not ignored inline. `Any` is a flagged exception, not a habit.
- Data at boundaries: `dataclasses` (internal) / `pydantic` (parsing
  external input); dicts don't cross module boundaries as pseudo-objects.
- `pathlib` over `os.path` · f-strings · context managers for every
  resource · comprehensions until they stop being readable · no mutable
  default arguments · explicit `__all__` or underscore-private convention.

## Errors
- Package-rooted exception hierarchy; catch narrowly; `raise X from err`
  to preserve cause; library code raises, application edges decide.
- `logging`, never `print`, in importable code.
- Terminal output ASCII-safe (or reconfigure stream encoding at entry):
  Windows cp1252 pipes crash on printed Unicode punctuation even when
  file I/O is correctly UTF-8.

## Testing
- `pytest` with output shown; `hypothesis` where the logic has algebra;
  fixtures over setup inheritance; markers for slow/integration tiers so
  the fast suite stays fast.

## Dependencies
- `pip-audit` (or `uv` audit tooling) in CI; prefer stdlib; every
  addition passes `standards/dependency-policy.md`.

## Review checklist add-ons
- [ ] Public functions fully hinted; typecheck clean on the diff
- [ ] External input parsed into typed models at the boundary
- [ ] Exceptions chained with `from`; nothing caught-and-ignored
- [ ] No mutable default args; resources under context managers
