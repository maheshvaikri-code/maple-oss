# MAPLE Agent Runtime Slice 151 QA Record

Date: 2026-08-28

## Scope

This record covers fail-fast bounded `SchedulingPolicy` construction. Strategy
names, concurrency, polling interval, finiteness, and preemption type are
validated before a scheduler worker can consume the policy.

## Functional evidence

- Focused scheduler/policy regression: `43 passed in 1.38s`.
- Full tracked task-management suite: `158 passed in 22.24s`.
- Full tracked repository manifest: `1391 passed, 1 skipped in 218.01s`.
- Coverage includes all invalid strategy/type/bound cases and acceptance of
  the documented upper bounds.

## Static and boundary evidence

- `python -m mypy maple --follow-imports=skip --ignore-missing-imports`:
  `Success: no issues found in 97 source files`.
- Changed-surface Black: `2 files would be left unchanged`.
- Changed-surface isort: passed.
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
- Targeted changed-surface scans are clean; the broad documentation scan was
  intentionally not treated as a secret scan because the API reference contains
  literal placeholder examples such as `api_key` and `auth_token`.

## Package evidence

The clean `git archive HEAD` package candidate built successfully as
`maple_oss-1.1.3`:

- `python -m build --wheel --sdist`: exit `0`;
- wheel: `104` archive entries;
- sdist: `640` archive entries;
- `twine check`: both artifacts `PASSED`;
- `pip install --no-deps --target ...`: exit `0`;
- isolated export smoke: `clean_archive_scheduler_policy_smoke=passed`;
- workspace-only archive entries: `0`.

The exact-`HEAD` archive is rebuilt after this QA and release-plan closure
metadata is committed.

## QA decision

The policy validation boundary is functionally ready for preview release. The
overall publish hold remains in place for environment-wide dependency
governance, unavailable Bandit, and the required independent verifier session.
