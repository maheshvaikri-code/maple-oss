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
- `git diff --check 84f8afa..HEAD`: passed.

## Dependency evidence

The current environment-wide `python -m pip_audit --progress-spinner off`
result is `384 known vulnerabilities in 77 packages`, with local non-PyPI
packages skipped. This remains a release veto outside this slice.

## Package evidence

The final `git archive HEAD` snapshot built successfully as `maple-oss-1.1.3`:

- build exit: `0`;
- wheel: `104` archive entries;
- sdist: `623` archive entries;
- `twine check`: both artifacts passed;
- `pip install --no-deps --target ...`: exit `0`;
- isolated export smoke: `clean_archive_memory_archive_boundary_smoke=passed`;
- workspace-only archive entries: `0`.

The first local smoke expression used an invalid one-line provider test double;
the corrected smoke against the installed clean artifact passed as recorded
above.

## QA decision

The memory archive durability slice is functionally ready for preview release.
The overall publish hold remains in place for the environment-wide dependency
audit, unavailable Bandit tool, and required independent verifier session.
