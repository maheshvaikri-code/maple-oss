# QA evidence - MAPLE agent-runtime slice 61

## Scope

CrewAI adapter tool boundaries for communication, resource requests, secure
links, priority mapping, and optional CrewAI imports.

## Results

- `python -m pytest tests/adapters/test_crewai_adapter.py -q --no-cov -p no:dash -p no:benchmark`
  -> `3 passed in 4.54s`.
- `python -m mypy --python-version 3.10 maple/adapters/crewai_adapter.py --ignore-missing-imports --follow-imports=skip`
  -> `Success: no issues found in 1 source file`.
- `python -m ruff check maple/adapters/crewai_adapter.py tests/adapters/test_crewai_adapter.py`
  -> `All checks passed!`.
- Black, isort, and compile checks -> pass.
- Aggregate explicit Python 3.10-target audit -> `Found 27 errors in 1 file
  (checked 93 source files)`.

## Open release gates

The remaining diagnostics are in the NATS broker adapter. The configured Python
3.8 versus installed mypy 2.3 target mismatch, dependency-audit disposition,
Bandit availability, full repository regression, and independent fresh-context
verification remain open. No external publication was performed.
