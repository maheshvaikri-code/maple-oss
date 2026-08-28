# MAPLE Agent Runtime Slice 146 QA Record

Date: 2026-08-28

## Scope

This record covers fail-closed summary archiving in
`MemoryManager.summarize_and_archive()`. Provider errors retain their existing
behavior. Episodic persistence errors are returned to the caller, and working
memory is cleared only after the archive succeeds.

## Functional evidence

- Focused memory regression: `29 passed in 0.32s`.
- The added regression uses a failing episodic archive and verifies the typed
  error, original working-memory key, and token usage remain available.
- Existing empty-memory no-op and no-provider behavior remain covered.

## Static and boundary evidence

- `python -m mypy maple --follow-imports=skip --ignore-missing-imports`:
  `Success: no issues found in 97 source files`.
- Changed-surface Black: `2 files would be left unchanged`.
- Changed-surface isort: passed.
- Changed-surface Ruff: `All checks passed!`.
- `python -m compileall -q maple`: passed.
- Changed-surface secret and dangerous-construct scans: no matches.
- Bandit was unavailable in the environment (`No module named bandit`); this
  is not treated as a pass.

No dependency was added. No external provider call, publication, deployment,
cloud action, or website update was performed.

## Full regression evidence

- Exact tracked test manifest: `1400 passed, 1 skipped in 231.02s`.
- `git diff --check 84f8afa..HEAD`: pending the final documentation commit;
  the committed range is checked again before closure.

## Dependency evidence

The current environment-wide `python -m pip_audit --progress-spinner off`
result is `384 known vulnerabilities in 77 packages`, with local non-PyPI
packages skipped. This remains a release veto outside this slice.

## Package evidence

The final clean archive must build wheel and sdist, pass Twine checks, install
without dependencies into an isolated target, and run a no-dependency memory
archive smoke test. Exact artifact counts are recorded after that run.

## QA decision

The memory archive durability slice is functionally ready for preview release.
The overall publish hold remains in place for the environment-wide dependency
audit, unavailable Bandit tool, and required independent verifier session.
