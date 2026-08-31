# Code Review - MAPLE Agent Runtime Slice 6 @ 4ead28d / 3a91c6d

**Reviewer role:** Code Reviewer  · **Date:** 2026-08-24
**Reviewed against:** [brief](../briefs/maple-agent-runtime-release.md),
[ADR-005](../adr/005-evaluation-provider-capabilities.md), and
[implementation plan](../plans/maple-agent-runtime-release.md)

## Scope

This slice adds declared provider capabilities and deterministic fallback
selection, plus a local evaluation harness for exact outputs, JSON schemas, and
ordered tool trajectories. The public evaluation symbols are exported from both
`maple.autonomy` and top-level `maple`.

## Findings

| # | Sev | Location | Finding | Resolution |
|---|---|---|---|---|
| 1 | MINOR | Provider capabilities | Capability inference from provider names would be unsafe as providers/models vary. | Callers must register explicit declarations; unknown capabilities do not satisfy requirements. |
| 2 | MINOR | Provider fallback | Initialization failures could leak provider exception text or credentials. | Fallback returns provider names attempted and exception-free structured errors. |
| 3 | MINOR | Evaluation reports | Actual outputs may contain secrets or excessive data. | Reports apply the shared redaction policy and byte bound before retaining actual values. |

## Verification evidence

```text
ruff check maple/autonomy/evaluation.py maple/llm/capabilities.py tests/autonomy/test_evaluation.py tests/llm/test_capabilities.py --output-format concise
All checks passed!

python -m pytest tests/llm/test_capabilities.py tests/autonomy/test_evaluation.py -q -o addopts=
7 passed, 1 warning in 0.02s

python -m pytest tests/llm tests/autonomy -q -o addopts=
160 passed, 1 warning in 0.19s

python -c "from maple import EvalCase, EvaluationHarness, ProviderRouter; print(EvalCase, EvaluationHarness, ProviderRouter)"
<class 'maple.autonomy.evaluation.EvalCase'> <class 'maple.autonomy.evaluation.EvaluationHarness'> <class 'maple.llm.capabilities.ProviderRouter'>

python -m compileall -q maple
exit code 0
```

The pytest warning is the existing `asyncio_mode` configuration warning when
plugin autoload is disabled. Existing aggregate Ruff debt in the package
initializers remains a separate release-hardening item.

## Verdict

- [x] Slice review pass: no open BLOCKER or MAJOR finding.
- [ ] Final release review: pending slice 7, release hardening, and independent
  fresh-context verifier availability.

The available environment has no separate fresh-agent session facility, so this
artifact records local review evidence and does not claim independent verifier
separation.
