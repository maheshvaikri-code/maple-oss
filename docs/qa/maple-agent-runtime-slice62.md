# QA evidence - MAPLE agent-runtime slice 62

## Scope

NATS broker optional-transport boundaries, including configuration defaults,
SDK/error fallbacks, message IDs/results, callbacks, and the synchronous wrapper
event loop.

## Results

- `python -m pytest tests/broker/test_nats_broker.py -q --no-cov -p no:dash -p no:benchmark`
  -> `1 passed, 1 skipped in 0.21s`; the integration check is skipped because
  `nats-py` is not installed.
- `python -m mypy --python-version 3.10 maple/broker/nats_broker.py --ignore-missing-imports --follow-imports=skip`
  -> `Success: no issues found in 1 source file`.
- `python -m ruff check maple/broker/nats_broker.py tests/broker/test_nats_broker.py`
  -> `All checks passed!`.
- Black, isort, and compile checks -> pass.
- Aggregate explicit Python 3.10-target audit -> `Success: no issues found
  in 93 source files`.

## Open release gates

The configured Python 3.8 versus installed mypy 2.3 target mismatch,
dependency-audit disposition, Bandit availability, full repository regression,
and independent fresh-context verification remain open. No external publication
was performed.
