# QA evidence — MAPLE agent-runtime slice 40

## Results

- `python -m pytest tests/core/test_serialization.py
  tests/llm/test_provider.py --no-cov` → `32 passed`.
- `python -m mypy --python-version 3.10 maple/core/serialization.py
  maple/llm/registry.py --ignore-missing-imports --follow-imports=skip` →
  `Success: no issues found in 2 source files`.
- Aggregate `python -m mypy --python-version 3.10 maple/ --ignore-missing-imports`
  → `198 errors in 31 files`, down from `201 errors in 33 files`.
- Black, isort, and compileall pass for the changed source files.

## Open gates

The full repository pytest run remains incomplete. The configured Python 3.8
mypy target is not accepted by installed mypy 2.3, so the support-matrix /
toolchain decision remains open. Direct Ruff on these legacy files still
reports pre-existing module-docstring/unused-import findings; the repository
Ruff gate covers `tools` and `tests` and remains clean. Bandit is unavailable
locally, dependency audit disposition is open, and fresh-context independent
verification is not available. No package was uploaded or published.
