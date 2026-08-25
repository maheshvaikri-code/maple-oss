# Slice 71 QA - Typed Tool Input/Output Contracts

**Role:** Backend / QA / Release
**Commit:** `ded4477`
**Date:** 2026-08-25

## Scope

Additive Pydantic-style `Tool.input_model` and `Tool.output_model` support.
Existing JSON-Schema tools retain their prior execution and validation path.

## Evidence

- Focused contract/tool/agent regression: `43 passed in 0.37s`.
- Full autonomy regression: `212 passed in 3.26s`.
- `python -m mypy maple/ --ignore-missing-imports`: `Success: no issues found
  in 93 source files`.
- `ruff check maple`: `All checks passed!`.
- `ruff check tools tests`: `All checks passed!`.
- `black --check maple`: `93 files would be left unchanged`.
- `isort --check-only maple`: `All done!`.
- `python -m compileall -q maple`: exit 0.
- Doctor: `ready: true`, `network: false`, version `1.1.3`, all eight checks
  true.
- Wheel and sdist built successfully; Twine reported `PASSED` for both.
- README and API-reference usage documentation was added in commit `9236bc4`.

## Boundary review

- Input models publish their JSON Schema to the LLM tool definition.
- Input validation happens before input guardrails and handler execution.
- Validated model fields are normalized into handler keyword arguments.
- Invalid input and model serialization failures return structured
  `TOOL_INPUT_INVALID` errors without invoking the handler.
- Output models validate handler results and return typed instances.
- Invalid output returns `TOOL_OUTPUT_INVALID` and does not reach output
  guardrails.

## Decision

PASS for the slice. No new dependency, publication, website mutation, or
external service action was introduced. The exact repository-wide suite and
fresh independent verifier gate remain open at the release level.
