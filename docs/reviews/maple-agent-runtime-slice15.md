# Code Review - MAPLE Agent Runtime Slice 15 @ working tree

**Reviewer role:** Code Reviewer  · **Date:** 2026-08-24
**Reviewed against:** [brief](../briefs/maple-agent-runtime-release.md),
[ADR-013](../adr/013-bounded-workflow-fan-out.md), and
[implementation plan](../plans/maple-agent-runtime-release.md)

## Scope

This slice adds `Workflow.add_fan_out(...)` with bounded trusted in-process
thread workers, independent JSON-safe branch snapshots, deterministic
declaration-order merging, state-key collision rejection, a checkpointed
fan-in boundary, and pause/resume behavior at the group boundary. It does not
claim process isolation, rollback, per-branch retry, replay, or cross-process
checkpoint leases.

## Findings

| # | Sev | Location | Finding | Suggested fix | Resolution |
|---|---|---|---|---|---|
| 1 | MINOR | `maple/autonomy/workflow.py` fan-out pause path | A pause before the group checkpoint can repeat source and branch side effects on resume. | Require idempotent handlers for external effects; move to per-branch durable checkpoints when retry/history semantics are designed. | Documented in ADR-013 and API reference; accepted as the explicit at-least-once boundary. |

## Scope check

The diff matches Slice 15. It adds no dependency, cloud call, website change,
publication action, or hard-sandbox claim. Branch execution is bounded by the
workflow configuration and the hard ceiling; branch output conflicts fail the
run instead of silently applying timing-dependent last-write-wins behavior.

## Verification evidence

```text
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'; python -m pytest tests/autonomy/test_workflow.py -q -o addopts=
13 passed, 1 warning in 0.06s

$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'; python -m pytest tests/llm tests/autonomy tests/test_cli.py -q -o addopts=
187 passed, 1 warning in 0.85s

ruff check maple/autonomy/workflow.py tests/autonomy/test_workflow.py
All checks passed!

flake8 maple/autonomy/workflow.py tests/autonomy/test_workflow.py --max-line-length=88 --extend-ignore=E203,W503,W291,W293,E302,E402,F401,F811,F841 --count --statistics
0

python -m compileall -q maple
exit code 0
```

The pytest warning is the existing `asyncio_mode` configuration warning when
plugin autoload is disabled. Independent fresh-context verifier sessions are
not available in this tool context, so this is local review evidence only.

## Verdict

- [x] Pass: no open BLOCKER or MAJOR finding.
- [ ] Return to build.
