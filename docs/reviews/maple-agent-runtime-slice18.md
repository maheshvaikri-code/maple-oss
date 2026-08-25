# Code Review - MAPLE Agent Runtime Slice 18 @ working tree

**Reviewer role:** Code Reviewer · **Date:** 2026-08-24
**Reviewed against:** [brief](../briefs/maple-agent-runtime-release.md),
[ADR-016](../adr/016-bounded-workflow-history.md), and
[implementation plan](../plans/maple-agent-runtime-release.md)

## Scope

This slice adds `HistoryCheckpointStore`, a bounded decorator that records
immutable checkpoint snapshots for current-process inspection while delegating
recovery and optimistic version checks to the wrapped store. It does not run
handlers, replay side effects, or claim restart/cross-process durability.

## Findings

| # | Sev | Location | Finding | Suggested fix | Resolution |
|---|---|---|---|---|---|
| 1 | MINOR | History retention | The decorator's history is process-local even when the wrapped store is file-backed. | Add a durable history backend when replay/retention requirements and a cross-process contract are defined. | Explicitly documented in ADR-016 and API reference; accepted for inspection tooling. |
| 2 | MINOR | Replay semantics | Re-running arbitrary node handlers could duplicate external side effects. | Require replay-safe effects/idempotency or a dry-run executor before implementing replay. | Replay is explicitly out of scope; history is data-only. |

## Scope check

The diff matches Slice 18. It adds no dependency, cloud call, website change,
publication action, handler execution path, or recovery schema change. History
copies are JSON-safe and bounded; the wrapped store remains authoritative.

## Verification evidence

```text
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'; python -m pytest tests/autonomy/test_workflow.py -q -o addopts=
16 passed, 1 warning in 0.10s

$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'; python -m pytest tests/llm tests/autonomy tests/test_cli.py -q -o addopts=
199 passed, 1 warning in 0.86s

ruff check maple/autonomy/workflow.py tests/autonomy/test_workflow.py
All checks passed!

python -m flake8 maple/autonomy/workflow.py tests/autonomy/test_workflow.py --max-line-length=88 --extend-ignore=E203,W503,W291,W293,E302,E402,F401,F811,F841 --count --statistics
0

python -m compileall -q maple
compileall exit code: 0

python -m maple.cli doctor --json
{"checks": {"core": true, "evaluation": true, "events": true, "execution": true, "interop": true, "retrieval": true}, "network": false, "ready": true, "status": "SUCCESS", "version": "1.1.3"}

python -m build --no-isolation --wheel --sdist --outdir '.tmp-maple-history-final'
Successfully built maple_oss-1.1.3-py3-none-any.whl and maple_oss-1.1.3.tar.gz

python -m twine check '.tmp-maple-history-final\*'
Checking .tmp-maple-history-final\maple_oss-1.1.3-py3-none-any.whl: PASSED
Checking .tmp-maple-history-final\maple_oss-1.1.3.tar.gz: PASSED
```

The pytest warning is the existing `asyncio_mode` configuration warning when
plugin autoload is disabled. Independent fresh-context verifier sessions are
not available in this tool context, so this is local review evidence only.

## Verdict

- [x] Pass: no open BLOCKER or MAJOR finding.
- [ ] Return to build.
