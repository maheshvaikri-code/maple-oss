# QA evidence — MAPLE agent-runtime slice 31

## Results

- `python -m pytest tests/resources -q -o addopts=` → `92 passed in 0.30s`.
- Explicit Python 3.10-target mypy passed for specification, manager,
  negotiation, and lease modules; the known Python 3.8 configuration warning
  is emitted by installed mypy 2.3.
- Black, isort, Ruff, and compile checks passed on the changed resource
  modules.
- `git diff --check` passed before commit.
- Aggregate audit: `Found 277 errors in 43 files (checked 93 source files)`.

## Open gates

Full-repository pytest completion, dependency/security audit disposition,
installed Bandit availability, and fresh-context independent verification
remain open.
