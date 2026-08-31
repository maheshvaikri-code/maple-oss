# MAPLE Agent Runtime Slice 155 QA Record

Date: 2026-08-28

## Scope

This record covers ownership-checked local task failure. `TaskQueue` validates
the assigned owner, active state, and bounded error before recording `FAILED`;
`TaskScheduler` releases local capacity only after that queue transition.
Retry remains an explicit bounded `requeue_task()` operation.

## Functional evidence

- Focused scheduler/failure regression: `74 passed in 2.02s`.
- Full tracked task-management suite: `167 passed in 22.33s`.
- Full tracked repository test manifest: `1400 passed, 1 skipped in 211.56s`.
- Coverage includes successful failure acknowledgement, `ASSIGNED` and
  `RUNNING` ownership semantics, error recording, wrong-owner rejection,
  oversized-error rejection, unchanged assignment/load state, and explicit
  retry separation.

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
- sdist: `652` archive entries;
- `twine check`: both artifacts `PASSED`;
- `pip install --no-deps --target ...`: exit `0`;
- isolated export smoke: `clean_archive_task_failure_smoke=passed`;
- workspace-only archive entries: `0`.

The exact-`HEAD` archive is rebuilt after this QA and release-plan closure
metadata is committed.

## QA decision

The ownership-checked failure boundary is functionally ready for preview
release. The overall publish hold remains in place for environment-wide
dependency governance, unavailable Bandit, and the required independent
verifier session.
