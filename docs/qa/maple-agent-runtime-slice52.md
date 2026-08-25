# QA evidence — MAPLE agent-runtime slice 52

## Scope

Constructor and JSON decode boundaries for the legacy A2A, ACP, and FIPA ACL
adapters:

- `maple/adapters/a2a_adapter.py`
- `maple/adapters/acp_adapter.py`
- `maple/adapters/fipa_acl_adapter.py`

## Results

- `python -m mypy --python-version 3.10 maple/adapters/a2a_adapter.py maple/adapters/acp_adapter.py maple/adapters/fipa_acl_adapter.py --ignore-missing-imports --follow-imports=skip` → `Success: no issues found in 3 source files`.
- `python -m black --check ...` for the three changed adapters → pass.
- `python -m isort --check-only ...` for the three changed adapters → pass.
- `python -m compileall -q ...` for the three changed adapters → pass.
- Import smoke for all three adapter classes → `interop adapter imports passed`.
- No dedicated A2A, ACP, or FIPA ACL adapter tests are present in `tests/`.
- Aggregate explicit Python 3.10-target audit → `Found 132 errors in 12 files (checked 93 source files)`.

## Open release gates

The aggregate legacy type debt, configured Python 3.8 versus installed mypy 2.3
target mismatch, dependency-audit disposition, Bandit availability, full
repository regression completion, and independent fresh-context verification
remain open. No external publication was performed.
