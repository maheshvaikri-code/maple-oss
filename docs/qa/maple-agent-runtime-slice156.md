# MAPLE Agent Runtime Slice 156 QA Record

Date: 2026-08-28

## Scope

This record covers fail-closed pending-request state for durable agent-run
checkpoints. `AgentRunCheckpoint` normalization now rejects ambiguous request
IDs and status combinations before an in-memory or file-backed store mutates
its current record.

## Functional evidence

- Focused run/lease regression: `34 passed in 0.22s`.
- Full autonomy suite with the repository async plugin enabled: `457 passed
  in 18.69s`.
- Full tracked repository test manifest: `1458 passed, 1 skipped in 220.84s`.
- The isolated package smoke confirmed parser rejection and store mutation
  protection: `clean_archive_checkpoint_invariant_smoke=passed`.
- Coverage includes paused-without-request, non-paused-with-request, terminal
  pending state, both pending IDs, both valid paused request types, and
  unchanged store state after rejection.

## Static and boundary evidence

- `python -m mypy maple --follow-imports=skip --ignore-missing-imports`:
  `Success: no issues found in 97 source files`.
- Changed-source Black: `3 files would be left unchanged`.
- Changed-source isort: passed.
- Changed-surface Ruff: `All checks passed!`.
- `python -m compileall -q maple`: passed.
- Changed-surface dangerous-construct scan:
  `changed_surface_dangerous_construct_scan=clean`.
- Changed-source secret scan: `targeted_changed_source_secret_scan=clean`.

The whole-worktree `git diff --check` still reports one pre-existing trailing
whitespace line in the user-owned `demo_package/launch_demos.py`; it was not
changed by this slice.

No dependency was added. No external provider call, publication, deployment,
cloud action, or website update was performed.

## Dependency and security evidence

- `python -m pip_audit --progress-spinner off` remains an environment-wide
  release veto at `384 known vulnerabilities in 77 packages`; local
  non-PyPI packages were skipped.
- Bandit remains unavailable in the environment (`No module named bandit`);
  no Bandit pass is claimed.
- The changed-surface scans above are clean.

## Package evidence

The exact committed-HEAD archive candidate was built and installed in an
isolated target:

- `python -m build --wheel --sdist`: exit `0`;
- wheel: `104` archive entries;
- sdist: `655` archive entries;
- `twine check`: both artifacts `PASSED`;
- `pip install --no-deps --target ...`: exit `0`;
- isolated export smoke: `clean_archive_checkpoint_export_smoke=passed`;
- isolated invariant smoke: `clean_archive_checkpoint_invariant_smoke=passed`;
- workspace-only archive entries: `0`.

## QA decision

The local checkpoint-integrity boundary is functionally ready for preview
release. The overall publish hold remains in place for environment-wide
dependency governance, unavailable Bandit, and the required independent
verifier session.
