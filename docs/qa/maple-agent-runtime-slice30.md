# QA evidence — MAPLE agent-runtime slice 30

## Results

- `python -m pytest tests/broker -q -o addopts=` → `62 passed in 1.25s`.
- `python -m pytest tests/adapters/test_mcp_adapter.py tests/autonomy/test_mcp_tools.py tests/autonomy/test_mcp_governance.py -q -o addopts=` → `17 passed in 0.24s`.
- Explicit Python 3.10-target mypy passed for broker core/queue/routing,
  production broker, and the MCP adapter. The known configured Python 3.8
  warning is emitted by installed mypy 2.3.
- Black, isort, Ruff, and compile checks passed on the changed broker/MCP
  modules and the new regression test.
- `git diff --check` passed before commit.
- Aggregate audit: `Found 287 errors in 44 files (checked 93 source files)`.

## Open gates

The full repository suite remains incomplete; unavailable Bandit, dependency
audit disposition, and fresh-context independent verification remain open.
