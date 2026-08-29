# Code Review — Slice 202 local session-ID correction @ b6ef016

**Reviewer role:** Code Reviewer · **Date:** 2026-08-29  
**Reviewed against:** [Slice 202 brief](../briefs/maple-agent-runtime-slice202.md),
[Slice 202 plan](../plans/maple-agent-runtime-slice202.md), and the direct
session-store contract in [API reference](../api-reference.md)

**Execution limitation:** this environment cannot create the fresh independent
verifier sessions required by the repository doctrine. This is a same-context
review of the committed diff, not independent approval.

**Executed:**

```text
python -m pytest tests/autonomy/test_sessions.py -q --no-cov
============================= 20 passed in 0.45s ==============================

python -m black --check --diff maple/
101 files would be left unchanged.

python -m isort --check-only --diff maple/
exit 0

python -m ruff check maple/autonomy/sessions.py tests/autonomy/test_sessions.py
All checks passed!

python -m mypy maple/ --ignore-missing-imports
Success: no issues found in 101 source files

python -m compileall -q maple tests
compileall: ok

python -m pytest tests -q --no-cov
1807 passed, 1 skipped in 360.69s (0:06:00)
```

## Findings

| # | Sev | Location | Finding | Suggested fix | Resolution |
|---|---|---|---|---|---|
| — | — | `maple/autonomy/sessions.py:1019,1201,1397,1521` | Explicit empty create/fork IDs were previously treated as omitted IDs and silently replaced with generated IDs. The correction preserves `None` generation while routing explicit values through the existing identifier validator. | — | clean at `b6ef016` |

## Scope check

The diff changes only ID resolution for built-in in-memory and file-backed
session creation/forking and adds regressions covering both implementations.
It does not add routes, scopes, dependencies, storage formats, message replay,
execution, or external actions. The focused tests prove invalid calls do not
consume configured session capacity because subsequent valid operations
succeed.

## Verdict

- [x] Pass for this same-context review (0 BLOCKER, MAJOR, MINOR, or NIT findings)
- [ ] Return to build — findings above

The independent fresh verifier remains unavailable and is not represented as
complete approval.
