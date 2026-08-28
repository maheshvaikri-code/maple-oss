# MAPLE Agent Runtime Slice 147 QA Record

Date: 2026-08-28

## Scope

This record covers bounded `EpisodicMemory` admission. Task IDs, serialized
event bytes, and per-task retained events are bounded before persistence.
Accepted records retain the newest window; invalid, oversized, or malformed
state returns typed errors without silently replacing data.

## Functional evidence

- Focused memory regression: `38 passed in 0.28s`.
- Coverage includes constructor limit validation, newest-event retention,
  oversized-event rejection without a write, invalid event/task data, and
  existing record/recall integration.
- Exact tracked test manifest: `1409 passed, 1 skipped in 241.21s`.

## Static and boundary evidence

- `python -m mypy maple --follow-imports=skip --ignore-missing-imports`:
  `Success: no issues found in 97 source files`.
- Changed-surface Black: `2 files would be left unchanged`.
- Changed-surface isort: passed.
- Changed-surface Ruff: `All checks passed!`.
- `python -m compileall -q maple`: passed.
- `git diff --check 84f8afa..HEAD`: pending the final slice 147 commits;
  the final committed range is checked again before closure.
- Changed-surface secret scan: `no matches`.
- Changed-surface dangerous-construct scan: `no matches`.
- Bandit is unavailable in the environment (`No module named bandit`); this is
  not treated as a pass.

No dependency was added. No external provider call, publication, deployment,
cloud action, or website update was performed.

## Dependency evidence

The current environment-wide `python -m pip_audit --progress-spinner off`
result is `384 known vulnerabilities in 77 packages`, with local non-PyPI
packages skipped. This remains a release veto outside this slice.

## Package evidence

The final clean archive must build wheel and sdist, pass Twine checks, install
without dependencies into an isolated target, run an episodic-memory export
smoke test, and contain no workspace-only files. Exact results are recorded
after that run.

## QA decision

The bounded episodic-memory slice is functionally ready for preview release
once its final exact-suite and clean-archive evidence is filed. The overall
publish hold remains in place for the environment-wide dependency audit,
unavailable Bandit tool, and required independent verifier session.
