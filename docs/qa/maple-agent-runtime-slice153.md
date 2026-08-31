# MAPLE Agent Runtime Slice 153 QA Record

Date: 2026-08-28

## Scope

This record covers atomic local task reassignment. `TaskQueue` now provides a
queue-locked ownership transfer for `ASSIGNED` tasks, and
`TaskScheduler.rebalance_loads()` changes local capacity bookkeeping only after
that transfer succeeds. `RUNNING` tasks remain pinned.

## Functional evidence

- Focused scheduler/reassignment regression: `70 passed in 1.97s`.
- Full tracked task-management suite: `163 passed in 22.26s`.
- Full tracked repository test manifest: `1396 passed, 1 skipped in 251.10s`.
- Coverage includes successful rebalancing transfer, owner preservation,
  running-task rejection, and unchanged local state on failed transitions.

## Static and boundary evidence

- `python -m mypy maple --follow-imports=skip --ignore-missing-imports`:
  `Success: no issues found in 97 source files`.
- Changed-source Black: `2 files would be left unchanged`.
- Changed-source isort: passed.
- Changed-surface Ruff: `All checks passed!`.
- `python -m compileall -q maple`: passed.
- Feature-surface diff check: passed.
- Targeted changed-surface secret scan: `targeted_secret_scan=clean`.
- Targeted changed-surface dangerous-construct scan:
  `dangerous_construct_scan=clean`.

No dependency was added. No external provider call, publication, deployment,
cloud action, or website update was performed.

## Dependency and security evidence

- `python -m pip_audit --progress-spinner off` remains an environment-wide
  release veto at `384 known vulnerabilities in 77 packages`; local non-PyPI
  packages were skipped.
- Bandit is unavailable in the environment (`No module named bandit`); this is
  not treated as a pass.
- Targeted changed-surface scans are clean.

## Package evidence

The clean `git archive HEAD` package candidate built successfully as
`maple_oss-1.1.3`:

- `python -m build --wheel --sdist`: exit `0`;
- wheel: `104` archive entries;
- sdist: `646` archive entries;
- `twine check`: both artifacts `PASSED`;
- `pip install --no-deps --target ...`: exit `0`;
- isolated export smoke: `clean_archive_task_reassignment_smoke=passed`;
- workspace-only archive entries: `0`.

The exact-`HEAD` archive is rebuilt after this QA and release-plan closure
metadata is committed.

## QA decision

The atomic reassignment boundary is functionally ready for preview release.
The overall publish hold remains in place for environment-wide dependency
governance, unavailable Bandit, and the required independent verifier session.
