# QA evidence — MAPLE agent-runtime slice 45

## Scope

Communication pattern type boundaries in publish-subscribe, request-response,
and streaming. The changes preserve the existing transport and delivery paths;
the direct publish result is normalized to the declared string message-ID
contract.

## Results

- `python -m pytest tests/communication/test_pubsub.py tests/communication/test_request_response.py tests/communication/test_streaming.py --no-cov` → `49 passed in 1.18s`.
- `python -m mypy --python-version 3.10 maple/communication/pubsub.py maple/communication/request_response.py maple/communication/streaming.py --ignore-missing-imports --follow-imports=skip` → `Success: no issues found in 3 source files`.
- `python -m black --check maple/communication/pubsub.py maple/communication/request_response.py maple/communication/streaming.py tests/communication/test_pubsub.py` → pass.
- `python -m isort --check-only maple/communication/pubsub.py maple/communication/request_response.py maple/communication/streaming.py tests/communication/test_pubsub.py` → pass.
- `python -m compileall -q maple` → pass.
- Aggregate explicit Python 3.10-target audit → `Found 152 errors in 22 files (checked 93 source files)`.

## Regression coverage

`test_direct_publish_returns_string_message_id` covers the brokerless direct
publish path and verifies the public `Result[str, ...]` contract. Existing
request-response timeout/error handling and stream subscription behavior remain
covered by the same focused suite.

## Open release gates

The aggregate legacy type debt, configured Python 3.8 versus installed mypy 2.3
target mismatch, dependency-audit disposition, Bandit availability, full
repository regression completion, and independent fresh-context verification
remain open. No external publication was performed.
