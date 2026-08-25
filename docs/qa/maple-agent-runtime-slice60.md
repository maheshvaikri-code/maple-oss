# QA evidence - MAPLE agent-runtime slice 60

## Scope

LangGraph adapter recovery decisions and optional LangGraph/LangChain SDK
fallback boundaries.

## Results

- `python -m pytest tests/adapters/test_langgraph_adapter.py -q --no-cov -p no:dash -p no:benchmark`
  -> `3 passed in 0.34s`.
- `python -m mypy --python-version 3.10 maple/adapters/langgraph_adapter.py --ignore-missing-imports --follow-imports=skip`
  -> `Success: no issues found in 1 source file`.
- `python -m ruff check maple/adapters/langgraph_adapter.py tests/adapters/test_langgraph_adapter.py`
  -> `All checks passed!`.
- Black, isort, and compile checks -> pass.
- Aggregate explicit Python 3.10-target audit -> `Found 42 errors in 3 files
  (checked 93 source files)`.

## Open release gates

Remaining diagnostics are in CrewAI, broker core, and NATS broker surfaces. The
configured Python 3.8 versus installed mypy 2.3 target mismatch,
dependency-audit disposition, Bandit availability, full repository regression,
and independent fresh-context verification remain open. No external publication
was performed.
