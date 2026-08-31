# MAPLE Agent Runtime Slice 148 QA Record

Date: 2026-08-28

## Scope

This record covers fail-closed `EpisodicMemory.search()` input and state
handling. Query text and result limits are bounded before scanning; store list
and read failures and malformed histories are returned instead of hidden.

## Functional evidence

- Focused memory regression: `49 passed in 0.29s`.
- Coverage includes invalid/oversized query text, invalid result limits, list
  and read error propagation, malformed stored history, and successful
  keyword matching.
- Exact tracked test manifest: `1420 passed, 1 skipped in 232.51s`.

## Static and boundary evidence

- `python -m mypy maple --follow-imports=skip --ignore-missing-imports`:
  `Success: no issues found in 97 source files`.
- Changed-surface Black: `2 files would be left unchanged`.
- Changed-surface isort: passed.
- Changed-surface Ruff: `All checks passed!`.
- `python -m compileall -q maple`: passed.
- Committed-range whitespace check: passed.
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

The final `git archive HEAD` snapshot built successfully as `maple-oss-1.1.3`:

- build exit: `0`;
- wheel: `104` archive entries;
- sdist: `629` archive entries;
- `twine check`: both artifacts passed;
- `pip install --no-deps --target ...`: exit `0`;
- isolated export smoke: `clean_archive_episodic_search_smoke=passed`;
- workspace-only archive entries: `0`.

## QA decision

The episodic-search boundary is functionally ready for preview release once
the final evidence is filed. The overall publish hold remains in place for the
environment-wide dependency audit, unavailable Bandit tool, and required
independent verifier session.
