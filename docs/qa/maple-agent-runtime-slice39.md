# QA evidence — MAPLE agent-runtime slice 39

## Results

- `python -m pytest tests/test_cli.py tests/test_basic.py --no-cov` →
  `8 passed`.
- `python -m mypy --python-version 3.10 maple/cli.py maple/__init__.py
  --ignore-missing-imports --follow-imports=skip` → `Success: no issues found
  in 2 source files`.
- Aggregate `python -m mypy --python-version 3.10 maple/ --ignore-missing-imports`
  → `201 errors in 33 files`, down from `205 errors in 35 files`.
- Black, isort, and compileall pass for the changed source files.

## Open gates

The full repository pytest run remains incomplete. The configured Python 3.8
mypy target is not accepted by installed mypy 2.3, so the support-matrix /
toolchain decision remains open. Bandit is unavailable locally, dependency
audit disposition is open, and fresh-context independent verification is not
available. No package was uploaded or published.
