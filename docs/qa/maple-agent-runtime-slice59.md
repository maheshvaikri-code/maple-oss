# QA evidence - MAPLE agent-runtime slice 59

## Scope

The OpenAI SDK adapter's `maple_resource_request` function boundary, including
injected resource allocation, validation, and missing-service behavior.

## Results

- `python -m pytest tests/adapters/test_openai_sdk_adapter.py -q --no-cov -p no:dash -p no:benchmark`
  -> `2 passed in 0.49s`.
- `python -m mypy --python-version 3.10 maple/adapters/openai_sdk_adapter.py --ignore-missing-imports --follow-imports=skip`
  -> `Success: no issues found in 1 source file`.
- `python -m ruff check maple/adapters/openai_sdk_adapter.py tests/adapters/test_openai_sdk_adapter.py`
  -> `All checks passed!`.
- Black, isort, and compile checks -> pass.
- Aggregate explicit Python 3.10-target audit -> `Found 51 errors in 4 files
  (checked 93 source files)`.

## Open release gates

Remaining diagnostics are in CrewAI, LangGraph, broker core, and NATS broker
surfaces. The configured Python 3.8 versus installed mypy 2.3 target mismatch,
dependency-audit disposition, Bandit availability, full repository regression,
and independent fresh-context verification remain open. No external publication
was performed.
