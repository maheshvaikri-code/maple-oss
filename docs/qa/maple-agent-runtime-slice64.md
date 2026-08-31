# QA evidence - MAPLE agent-runtime slice 64

## Scope

Harden the A2A registry request, dependency-free MCP URL boundary, and pickle
deserialization path against the blocking Bandit findings.

## Results

- Security regression (`tests/adapters/test_a2a_adapter.py`, MCP live
  discovery, and core serialization) -> `37 passed in 0.82s`.
- Cross-surface regression -> `621 passed, 1 skipped in 170.54s`; the skipped
  case is the optional live NATS check because `nats-py` is unavailable.
- Default mypy -> `Success: no issues found in 93 source files`.
- `python -m ruff check tools tests` -> `All checks passed!`.
- Black -> `93 files would be left unchanged.`; isort and compile pass.
- Isolated `.[dev,security]` environment -> `No broken requirements found`.
- Isolated `pip-audit` -> `No known vulnerabilities found`.
- Isolated Bandit `-ll` -> exit 0; no medium/high findings.

## Low-severity disposition

The full Bandit inventory contains 35 low-severity legacy findings:
B101 x1, B105 x4, B110 x22, B112 x3, B311 x3, B403 x1, and B405 x1. They are
non-blocking debt in pre-existing adapters, cleanup paths, pseudo-random IDs,
placeholder audit strings, and the intentionally retained pickle import; they
are recorded rather than hidden. No high or medium finding remains.

## Open release gates

The repository-wide test command still needs a terminal pytest summary, broad
legacy Maple Ruff cleanup remains open, and independent fresh-context
verification is unavailable in this tool context. No external publication or
website change was performed.
