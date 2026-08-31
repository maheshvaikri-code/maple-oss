# MAPLE Agent Runtime Slice 157 QA Record

Date: 2026-08-28

## Scope

This record covers fail-closed correlation between durable approval or
human-input records and the persisted tool-result placeholder. Sync and async
resume now validate the request's `tool_call_id` before waiting, consuming,
replaying, or executing the request.

## Functional evidence

- Focused durable-run regression: `36 passed in 0.41s`.
- Full autonomy suite with the repository async plugin enabled: `461 passed
  in 18.90s`.
- Full tracked repository test manifest: `1462 passed, 1 skipped in 244.26s`.
- Coverage proves mismatched sync/async approval requests return
  `RUN_PENDING_TOOL_MISSING` without invoking the handler, and mismatched
  sync/async human-input requests return the same error without consuming the
  response or clearing the checkpoint.

## Static and boundary evidence

- `python -m mypy maple --follow-imports=skip --ignore-missing-imports`:
  `Success: no issues found in 97 source files`.
- Changed-source Black: `2 files would be left unchanged`.
- Changed-source isort: passed.
- Changed-surface Ruff: `All checks passed!`.
- `python -m compileall -q maple`: passed.
- Changed-surface dangerous-construct scan: clean.
- Changed-source secret scan: clean.

The whole-worktree `git diff --check` continues to report one pre-existing
trailing whitespace line in the user-owned `demo_package/launch_demos.py`; it
was not changed by this slice.

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
- sdist: `658` archive entries;
- `twine check`: both artifacts `PASSED`;
- `pip install --no-deps --target ...`: exit `0`;
- isolated export smoke: `clean_archive_pending_tool_correlation_smoke=passed`;
- isolated correlation smoke: `clean_archive_pending_tool_correlation_invariant_smoke=passed`;
- workspace-only archive entries: `0`.

## QA decision

The local pending-request correlation boundary is functionally ready for
preview release. The overall publish hold remains in place for environment-wide
dependency governance, unavailable Bandit, and the required independent
verifier session.
