# Code Review - MAPLE Agent Runtime Slice 22 @ `a682656`

**Reviewer role:** Code Reviewer · **Date:** 2026-08-24  
**Reviewed against:** [ADR-020](../adr/020-deterministic-retrieval-evaluation.md)
and [implementation plan](../plans/maple-agent-runtime-release.md)

## Scope

This slice adds a dependency-free retrieval/source evaluation contract to the
existing evaluation harness. Golden cases declare bounded expected source
URIs and precision/recall thresholds; lexical and vector retrieval hits are
accepted through one API. The slice adds no model judge, network call,
embedding dependency, or answer-faithfulness claim.

## Findings

| # | Sev | Location | Finding | Suggested fix | Resolution |
|---|---|---|---|---|---|
| 1 | [MAJOR] | `RetrievalEvalCase.validate` / `EvaluationHarness.run_retrieval` | Unhashable golden URI values could raise during duplicate detection, and a host runner could return an unbounded hit sequence. | Validate URI types before set operations and enforce a retrieval-hit quota. | Fixed before commit `a682656`; regressions added for unhashable URIs and the hit limit. |

## Scope check

The diff matches Slice 22. Source URIs are deduplicated before computing
precision, recall, and F1; malformed hit types, invalid source URIs, runner
errors, exceptions, and quota breaches become typed per-case failures. The
existing generic output/schema/trajectory harness is unchanged. Documentation
explicitly separates retrieval coverage from generated-answer faithfulness.

## Verification evidence

```text
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'; python -m pytest tests/autonomy/test_evaluation.py -q -o addopts=
10 passed, 1 warning in 0.04s

$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'; python -m pytest tests/llm tests/autonomy tests/test_cli.py -q -o addopts=
225 passed, 1 warning in 3.00s

python -m ruff check maple/autonomy/evaluation.py tests/autonomy/test_evaluation.py --output-format concise
All checks passed!

python -m flake8 maple/autonomy/evaluation.py tests/autonomy/test_evaluation.py --max-line-length=88 --extend-ignore=E203,W503,W291,W293,E302,E402,F401,F811,F841 --count --statistics
0

python -m compileall -q maple
COMPILE_EXIT=0

python -m maple.cli doctor --json
{"checks": {"core": true, "evaluation": true, "events": true, "execution": true, "interop": true, "retrieval": true, "server": true, "sessions": true}, "network": false, "ready": true, "status": "SUCCESS", "version": "1.1.3"}

python -m twine check .tmp-maple-slice22-final\maple_oss-1.1.3-py3-none-any.whl .tmp-maple-slice22-final\maple_oss-1.1.3.tar.gz
Checking ...maple_oss-1.1.3-py3-none-any.whl: PASSED
Checking ...maple_oss-1.1.3.tar.gz: PASSED
```

Independent fresh verifier sessions were unavailable in this tool context;
this is the local G4 review record.

## Verdict

- [x] Pass: no open BLOCKER or MAJOR finding.
- [ ] Return to build.
