# QA evidence — MAPLE agent-runtime slice 56

## Scope

Intentional fallback classes and public compatibility exports in
`maple/security/__init__.py`.

## Results

- `python -m pytest tests/security/test_security_init.py --no-cov` → `30 passed in 0.72s`.
- `python -m mypy --python-version 3.10 maple/security/__init__.py --ignore-missing-imports --follow-imports=skip` → `Success: no issues found in 1 source file`.
- `python -m black --check maple/security/__init__.py` → pass.
- `python -m isort --check-only maple/security/__init__.py` → pass.
- `python -m compileall -q maple/security/__init__.py` → pass.
- Aggregate explicit Python 3.10-target audit → `Found 95 errors in 8 files (checked 93 source files)`.

## Open release gates

The aggregate legacy type debt, configured Python 3.8 versus installed mypy 2.3
target mismatch, dependency-audit disposition, Bandit availability, full
repository regression completion, and independent fresh-context verification
remain open. No external publication was performed.
