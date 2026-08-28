# MAPLE Agent Runtime Slice 144 QA Record

Date: 2026-08-28

## Scope

This record covers declaration-driven async-completion capability routing.
`ProviderCapabilities(async_completion=True)` is matched by
`ProviderRequirements(async_completion=True)`; providers without that
explicit declaration are excluded. The router does not infer the capability
from arbitrary methods or inherited compatibility fallbacks.

## Functional evidence

- Focused capability/provider regression: `21 passed in 0.45s`.
- Exact tracked test manifest (`git ls-files tests`): `1390 passed, 1 skipped
  in 219.74s`.
- Offline routing coverage selects only the explicitly declared async provider
  and excludes a provider that exposes only the synchronous fallback.

## Static and boundary evidence

- `python -m mypy maple --follow-imports=skip --ignore-missing-imports`:
  `Success: no issues found in 97 source files`.
- Changed-surface Black: `2 files would be left unchanged`.
- Changed-surface isort: passed.
- Changed-surface Ruff: `All checks passed!`.
- `python -m compileall -q maple tests`: passed.
- `git diff --check b946496..HEAD`: passed.
- Committed-tree secret and dangerous-construct scans: zero matches.

No dependency was added. No external provider call, publication, deployment,
cloud action, or website update was performed.

## Package evidence

A clean `git archive HEAD` snapshot built successfully as `maple-oss-1.1.3`:

- wheel: `104` archive entries;
- sdist: `617` archive entries;
- `twine check`: both artifacts passed;
- `pip install --no-deps --target ...`: passed;
- isolated export smoke for `ProviderCapabilities`,
  `ProviderRequirements`, and `ProviderRouter`: passed.

## QA decision

The capability-routing slice is functionally and package-boundary ready. The
overall publish hold remains in place for environment-wide dependency
governance and independent verification.
