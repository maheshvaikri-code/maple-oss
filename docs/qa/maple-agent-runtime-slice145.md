# MAPLE Agent Runtime Slice 145 QA Record

Date: 2026-08-28

## Scope

This record covers bounded `WorkingMemory` admission and token accounting.
`WorkingMemory` validates the token budget, entry count, UTF-8 key/content
boundary, Unicode control characters, and relevance metadata before mutation.
Accepted entries preserve oldest-entry eviction; entries that cannot fit in the
complete budget fail before eviction.

## Functional evidence

- Focused working-memory regression: `28 passed in 0.29s`.
- Exact tracked test manifest after the final code change: `1399 passed, 1
  skipped in 238.67s`.
- Coverage includes invalid budgets, UTF-8 byte accounting, oversized-entry
  rejection without eviction, count bounds, C0/C1 control-key rejection,
  invalid content/relevance, and no-mutation guarantees.

## Static and boundary evidence

- `python -m mypy maple --follow-imports=skip --ignore-missing-imports`:
  `Success: no issues found in 97 source files`.
- Changed-surface Black: `2 files would be left unchanged`.
- Changed-surface isort: passed.
- Changed-surface Ruff: `All checks passed!`.
- `python -m compileall -q maple`: passed.
- `git diff --check e36c992..HEAD`: passed.
- Changed-surface secret scan: `no matches`.
- Changed-surface dangerous-construct scan: `no matches`.
- Bandit was unavailable in the environment (`No module named bandit`); this
  is not treated as a pass.

No dependency was added. No external provider call, publication, deployment,
cloud action, or website update was performed.

## Dependency evidence

`python -m pip_audit --progress-spinner off` reported `384 known
vulnerabilities in 77 packages`, and skipped local packages not found on
PyPI. This environment-wide result remains a release veto outside the memory
slice; the slice adds no dependency.

## Package evidence

The clean `git archive HEAD` snapshot built successfully as `maple-oss-1.1.3`:

- build exit: `0`;
- wheel: `104` archive entries;
- sdist: `620` archive entries;
- `twine check`: both artifacts passed;
- `pip install --no-deps --target ...`: exit `0`;
- isolated export smoke: `clean_archive_memory_smoke=passed`;
- workspace-only archive entries: `0`.

## QA decision

The bounded working-memory slice is functionally ready for preview release.
The overall publish hold remains in place for the environment-wide dependency
audit, unavailable Bandit tool, and required independent verifier session.
