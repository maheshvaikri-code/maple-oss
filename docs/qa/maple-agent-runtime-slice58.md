# QA evidence - MAPLE agent-runtime slice 58

## Scope

Optional OpenAI and Anthropic SDK configuration, compatible request payload
containers, and response parser boundaries in the LLM providers.

## Results

- `python -m pytest tests/llm/test_provider_native_streaming.py -q --no-cov`
  -> `3 passed in 0.23s`.
- `python -m mypy --python-version 3.10 maple/llm/openai_provider.py maple/llm/anthropic_provider.py --ignore-missing-imports --follow-imports=skip`
  -> `Success: no issues found in 2 source files`.
- `python -m black --check maple/llm/openai_provider.py maple/llm/anthropic_provider.py`
  -> pass.
- `python -m isort --check-only maple/llm/openai_provider.py maple/llm/anthropic_provider.py`
  -> pass.
- `python -m compileall -q maple/llm/openai_provider.py maple/llm/anthropic_provider.py`
  -> pass.
- Aggregate explicit Python 3.10-target audit -> `Found 62 errors in 5 files
  (checked 93 source files)`.

## Open release gates

The remaining broker/adapter type debt, configured Python 3.8 versus installed
mypy 2.3 target mismatch, dependency-audit disposition, Bandit availability,
full repository regression completion, and independent fresh-context
verification remain open. No external publication was performed.
