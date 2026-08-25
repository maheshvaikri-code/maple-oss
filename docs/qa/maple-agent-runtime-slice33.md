# QA evidence — MAPLE agent-runtime slice 33

## Results

- `python -m pytest tests/adapters/test_mcp_adapter.py tests/resources
  --no-cov` → `97 passed`.
- `python -m mypy --python-version 3.10 maple/adapters/mcp_adapter.py
  maple/resources/manager.py maple/resources/negotiation.py
  maple/resources/specification.py --ignore-missing-imports` → no diagnostics
  in the changed MCP/resource modules; the command still reports legacy
  imported-module debt outside this slice.
- Aggregate `python -m mypy --python-version 3.10 maple/ --ignore-missing-imports`
  → `266 errors in 40 files`, down from `277 errors in 43 files`.
- Black, isort, Ruff, and compileall pass for the changed source/test files.

## Open gates

The full repository pytest run remains incomplete. The configured Python 3.8
mypy target is not accepted by installed mypy 2.3, so the support-matrix /
toolchain decision remains open. Bandit is unavailable locally, dependency
audit disposition is open, and fresh-context independent verification is not
available. No package was uploaded or published.
