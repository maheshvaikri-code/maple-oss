# MAPLE Agent Runtime Slice 150 QA Record

Date: 2026-08-28

## Scope

This record covers the local scheduler assignment boundary. `TaskQueue`
atomically claims tasks for one agent, rejects invalid or duplicate ownership,
and `TaskScheduler` returns assignment failures through physical bounded retry
admission.

## Functional evidence

- Focused scheduler/lifecycle regression: `31 passed in 1.36s`.
- Full tracked task-management suite: `146 passed in 22.25s`.
- Full tracked repository test manifest: `1379 passed, 1 skipped in 212.36s`.
- Coverage includes physical scheduler rollback, duplicate ownership
  rejection, queue-side atomic assignment, and empty-owner validation.

## Static and boundary evidence

- `python -m mypy maple --follow-imports=skip --ignore-missing-imports`:
  `Success: no issues found in 97 source files`.
- Changed-surface Black: `3 files would be left unchanged`.
- Changed-surface isort: passed.
- Changed-surface Ruff: `All checks passed!`.
- `python -m compileall -q maple`: passed.
- Feature-surface whitespace check: passed.

No dependency was added. No external provider call, publication, deployment,
cloud action, or website update was performed.

## Dependency and security evidence

- `python -m pip_audit --progress-spinner off` remains an environment-wide
  release veto at `384 known vulnerabilities in 77 packages`; local non-PyPI
  packages were skipped.
- Bandit is unavailable in the environment (`No module named bandit`); this is
  not treated as a pass.
- Targeted changed-surface source scans found no new secrets or dangerous
  constructs.

## Package evidence

The clean `git archive HEAD` package candidate built successfully as
`maple-oss-1.1.3`:

- `python -m build --wheel --sdist`: exit `0`;
- wheel: `104` archive entries;
- sdist: `636` archive entries;
- `twine check`: both artifacts passed;
- `pip install --no-deps --target ...`: exit `0`;
- isolated export smoke: `clean_archive_scheduler_smoke=passed`;
- workspace-only archive entries: `0`.

The final exact-`HEAD` archive is rebuilt after this QA record and the release
plan closure metadata are committed.

## QA decision

The local scheduler assignment boundary is functionally ready for preview
release once the final exact tracked suite and clean-archive package gates are
recorded. The overall publish hold remains in place for environment-wide
dependency governance, unavailable Bandit, and the required independent
verifier session.
