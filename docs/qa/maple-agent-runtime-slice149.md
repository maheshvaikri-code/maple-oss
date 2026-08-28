# MAPLE Agent Runtime Slice 149 QA Record

Date: 2026-08-28

## Scope

This record covers bounded global `TaskQueue` admission and stale-entry
lifecycle handling. The queue validates its constructor capacity, enforces one
queued-item budget across all priorities, discards terminal stale tuples at
assignment, and rejects capacity-full requeues before state mutation.

## Functional evidence

- Focused queue/scheduler regression: `42 passed in 0.89s`.
- Full tracked task-management suite: `142 passed in 22.28s`.
- Full tracked repository test manifest: `1375 passed, 1 skipped in 234.42s`.
- Coverage includes invalid capacities, global cross-priority admission,
  stale cancelled/completed tuple suppression, and requeue state preservation
  when the global queue is full.

## Static and boundary evidence

- `python -m mypy maple --follow-imports=skip --ignore-missing-imports`:
  `Success: no issues found in 97 source files`.
- Changed implementation Black check: `1 file would be left unchanged`.
- Changed implementation isort check: passed.
- Changed-surface Ruff: `All checks passed!`.
- `python -m compileall -q maple`: passed.
- Feature-surface whitespace check: passed.

The existing task-submission regression file intentionally retains its
pre-existing non-Black formatting; no unrelated formatter rewrite was staged.
The broader working tree also contains user-owned demo changes, so a clean
whole-tree whitespace claim is not made.

An aggregate run that also included the five untracked user-owned Doctrine
test modules stalled without failure output and was interrupted. The tracked
runtime manifest above completed successfully; the untracked harness was not
included in the clean package candidate.

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

The clean `git archive HEAD` snapshot built successfully as `maple-oss-1.1.3`:

- `python -m build --wheel --sdist`: exit `0`;
- wheel: `104` archive entries;
- sdist: `632` archive entries;
- `twine check`: both artifacts passed;
- `pip install --no-deps --target ...`: exit `0`;
- isolated export smoke: `clean_archive_task_queue_smoke=passed`;
- workspace-only archive entries: `0`.

## QA decision

The local task-queue boundary is functionally ready for preview release once
the final exact tracked suite and clean-archive package gates are recorded.
The overall publish hold remains in place for environment-wide dependency
governance, unavailable Bandit, and the required independent verifier session.
