# QA evidence — MAPLE agent-runtime slice 54

## Scope

AutoGen adapter constructor, registry, group-chat input, and performance-metric
type boundaries in `maple/adapters/autogen_adapter.py`.

## Results

- `python -m mypy --python-version 3.10 maple/adapters/autogen_adapter.py --ignore-missing-imports --follow-imports=skip` → `Success: no issues found in 1 source file`.
- `python -m black --check maple/adapters/autogen_adapter.py` → pass.
- `python -m isort --check-only maple/adapters/autogen_adapter.py` → pass.
- `python -m compileall -q maple/adapters/autogen_adapter.py` → pass.
- Import smoke → `autogen adapter import status: True`.
- No dedicated AutoGen adapter tests are present in `tests/`.
- Aggregate explicit Python 3.10-target audit → `Found 126 errors in 10 files (checked 93 source files)`.

## Open release gates

The aggregate legacy type debt, configured Python 3.8 versus installed mypy 2.3
target mismatch, dependency-audit disposition, Bandit availability, full
repository regression completion, and independent fresh-context verification
remain open. No external publication was performed.
