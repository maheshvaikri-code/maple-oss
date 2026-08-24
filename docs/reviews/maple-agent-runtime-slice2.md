# Code Review - MAPLE Agent Runtime Slice 2 @ fed365f

**Reviewer role:** Code Reviewer  · **Date:** 2026-08-24  
**Reviewed against:** [brief](../briefs/maple-agent-runtime-release.md),
[ADR-001](../adr/001-maple-workflow-runtime.md), and
[implementation plan](../plans/maple-agent-runtime-release.md)

## Scope

This slice adds bounded JSON-Schema validation, structured model output
parsing, synchronous fail-closed guardrails, and tool input/output contracts.
The public surface is exported from `maple` and documented in the API
reference, README, and changelog. No dependency, website, cloud, or external
publication change was included.

## Findings

| # | Sev | Location | Finding | Resolution |
|---|---|---|---|---|
| 1 | MINOR | Tool failure boundary | Handler arguments were previously included in tool error details, which could expose secrets. | Removed arguments from the failure payload; only the tool name remains. |
| 2 | MINOR | Guardrail failure boundary | Guardrail exception text could disclose implementation or sensitive data. | Record only the exception type in the structured error. |
| 3 | MINOR | JSON-Schema `pattern` | Python's standard regex engine has no execution deadline. | Reject `pattern` explicitly instead of creating an unbounded validation path. |

## Verification evidence

```text
ruff check maple/autonomy/contracts.py maple/autonomy/tools.py maple/autonomy/agent.py tests/autonomy/test_contracts.py tests/autonomy/test_agent.py --output-format concise
All checks passed!

python -m pytest tests/autonomy/test_contracts.py tests/autonomy/test_tools.py tests/autonomy/test_agent.py -q -o addopts=
34 passed, 1 warning in 0.04s

python -m pytest tests/autonomy -q -o addopts=
107 passed, 1 warning in 0.11s

python -c "import maple; print(maple.Tool, maple.AutonomousConfig, maple.run_guardrails)"
<class 'maple.autonomy.tools.Tool'> <class 'maple.autonomy.agent.AutonomousConfig'> <function run_guardrails at ...>

python -m compileall -q maple
exit code 0
```

The pytest warning is the existing `asyncio_mode` configuration warning when
plugin autoload is disabled. The public package initializers still surface the
pre-existing aggregate Ruff debt; the new implementation and regression files
are clean, and initializer cleanup is deferred to release hardening.

## Verdict

- [x] Slice review pass: no open BLOCKER or MAJOR finding.
- [ ] Final release review: pending slices 3-8 and independent fresh-context
  verifier availability.

The available environment has no separate fresh-agent session facility, so this
artifact records local review evidence and does not claim independent verifier
separation.
