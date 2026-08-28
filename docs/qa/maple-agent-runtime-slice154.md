# MAPLE Agent Runtime Slice 154 QA Record

Date: 2026-08-28

## Scope

This record covers atomic local scheduler capacity admission. The scheduler
reserves one per-agent slot before the queue claim and rolls it back when the
claim fails, preventing concurrent over-admission without holding its lock
through queue callbacks.

## Functional evidence

- Focused scheduler/capacity regression: `71 passed in 2.35s`.
- Full tracked task-management suite: `164 passed in 23.18s`.
- Full tracked repository test manifest: `1397 passed, 1 skipped in 270.61s`.
- Coverage includes synchronized one-slot concurrent assignment, one accepted
  claim, one capacity rejection, rollback on rejected claims, and preserved
  scheduler load/task states.

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

The clean `git archive HEAD` package candidate will be recorded after the
slice-154 documentation and release-plan closure metadata are committed.

## QA decision

The atomic scheduler capacity boundary is functionally ready for preview
release. The overall publish hold remains in place for environment-wide
dependency governance, unavailable Bandit, and the required independent
verifier session.
