# Code Review - MAPLE agent runtime slice 25 @ `cd13435`

**Reviewer role:** Code Reviewer
**Date:** 2026-08-25
**Reviewed against:** [release plan](../plans/maple-agent-runtime-release.md) and the release-hardening criterion for a repository-wide Ruff gate

## Executed

```text
python -m ruff check tools tests
All checks passed!

python -m compileall -q tests
COMPILE_EXIT=0

$changed = @(git diff --name-only --diff-filter=AM | Where-Object { $_ -like 'tests/*.py' -or $_ -like 'tests/*/*.py' })
python -m pytest -q -o addopts= @changed
621 passed, 7 warnings in 62.47s (0:01:02)

python -m pytest tests/llm tests/autonomy tests/test_cli.py -q -o addopts=
240 passed in 3.35s
```

## Findings

| # | Sev | Location | Finding | Suggested fix | Resolution |
|---|-----|----------|---------|---------------|------------|
| 1 | MINOR | `tests/test_basic.py`, `tests/adapters/test_s2_adapter.py` | The changed-test gate still emits seven warnings: six `PytestReturnNotNoneWarning` instances from legacy boolean-returning tests and one deprecated event-loop warning. | Convert the legacy tests to assertion-style functions and use an explicit event loop in a follow-up slice. | Accepted follow-up; no blocker or major finding. |

The change is limited to test hygiene: safe unused-import cleanup,
behavior-preserving callback definitions, direct boolean assertions, explicit
legacy-header lint suppressions, and unused-value cleanup. The two import-smoke
tests retain their import checks with explicit `F401` annotations; the lint
cleanup did not weaken those checks.

No runtime MAPLE package code, public API, dependency, website, cloud, or
publication surface changed.

## Scope check

The committed diff contains only 38 tracked test files. User-owned untracked
Doctrine files (`AGENTS.md`, `CLAUDE.md`, `docs/brief.md`, `docs/maximus.md`,
`tests/test_doctrine_*.py`, and `tools/`) were not staged or modified.

An independent fresh-context verifier session was unavailable in this tool
environment; this report is the local role review and does not represent that
missing independent gate as complete.

## Verdict

- [x] Local review pass: 0 open BLOCKER/MAJOR findings.
- [ ] Independent fresh-context G4 verification complete.
