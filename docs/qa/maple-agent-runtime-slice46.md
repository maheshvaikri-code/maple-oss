# QA evidence — MAPLE agent-runtime slice 46

## Scope

Message-handler and handler-registry type boundaries in
`maple/agent/handlers.py`. The dispatch and registration paths are unchanged.

## Results

- `python -m pytest tests/agent/test_agent.py --no-cov` → `33 passed in 4.11s`.
- `python -m mypy --python-version 3.10 maple/agent/handlers.py --ignore-missing-imports --follow-imports=skip` → `Success: no issues found in 1 source file`.
- `python -m black --check maple/agent/handlers.py` → pass.
- `python -m isort --check-only maple/agent/handlers.py` → pass.
- `python -m compileall -q maple/agent/handlers.py` → pass.
- Aggregate explicit Python 3.10-target audit → `Found 150 errors in 21 files (checked 93 source files)`.

## Open release gates

The aggregate legacy type debt, configured Python 3.8 versus installed mypy 2.3
target mismatch, dependency-audit disposition, Bandit availability, full
repository regression completion, and independent fresh-context verification
remain open. No external publication was performed.
