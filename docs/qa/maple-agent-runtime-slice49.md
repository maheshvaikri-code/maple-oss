# QA evidence — MAPLE agent-runtime slice 49

## Scope

Recursive event redaction output containers in
`maple/autonomy/events.py`. Payload redaction, size limits, event retention,
and subscriber behavior are unchanged.

## Results

- `python -m pytest tests/autonomy/test_events.py --no-cov` → `5 passed in 0.20s`.
- `python -m mypy --python-version 3.10 maple/autonomy/events.py --ignore-missing-imports --follow-imports=skip` → `Success: no issues found in 1 source file`.
- `python -m black --check maple/autonomy/events.py` → pass.
- `python -m isort --check-only maple/autonomy/events.py` → pass.
- `python -m compileall -q maple/autonomy/events.py` → pass.
- Aggregate explicit Python 3.10-target audit → `Found 143 errors in 17 files (checked 93 source files)`.

## Open release gates

The aggregate legacy type debt, configured Python 3.8 versus installed mypy 2.3
target mismatch, dependency-audit disposition, Bandit availability, full
repository regression completion, and independent fresh-context verification
remain open. No external publication was performed.
