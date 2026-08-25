# QA + Security Report - MAPLE agent runtime slice 25 @ `cd13435`

**QA Engineer** · **Security Reviewer** · **Date:** 2026-08-25
**Build under test:** commit `cd13435` (`chore(quality): clear repository lint gate`)

## Acceptance criteria verification

| # | Criterion | How executed | Evidence | Pass |
|---|-----------|--------------|----------|------|
| 1 | The repository-wide Ruff gate passes without weakening the check. | Ran Ruff across `tools` and `tests`, including the user-owned untracked Doctrine files read-only. | `python -m ruff check tools tests` → `All checks passed!` | PASS |
| 2 | Lint cleanup preserves test behavior. | Ran all 38 changed tracked test files after restoring the two import-smoke checks. | `621 passed, 7 warnings in 62.47s (0:01:02)` | PASS |
| 3 | The focused MAPLE feature gate remains green. | Ran the established LLM/autonomy/CLI regression gate. | `240 passed in 3.35s` | PASS |
| 4 | The changed test surface remains syntactically valid. | Ran Python compilation over `tests`. | `COMPILE_EXIT=0` | PASS |

## Adversarial & edge matrix

| Input/scenario | Expected | Observed | Pass |
|----------------|----------|----------|------|
| Intentional import-smoke tests | Imports remain executed while Ruff is satisfied | Core import checks were restored and annotated with `F401`; changed tests pass | PASS |
| Callback identity/removal | Named callbacks preserve registration and removal identity | Broker, pub/sub, health, negotiation, and state callback tests pass | PASS |
| Boolean assertions | Equivalent truth semantics | Changed assertions pass in the 621-test surface | PASS |
| Unused-result side effects | Calls still execute even when return values are not asserted | Collector/task tests pass after removing only the unused bindings | PASS |
| User-owned untracked files | Remain unmodified and unstaged | `git status` shows them untracked; staged diff contains only 38 tracked test files | PASS |

## Regression

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

The unchanged one-command verifier was also exercised before this cleanup.
Its corpus lint gate passed, its pre-cleanup repository Ruff gate reported 154
findings, and its full unittest phase did not reach a summary during the
bounded observation window. That is not a full repository behavioral pass.

## Bugs found

No behavior bug was found in this slice. The review recorded seven warnings as
a follow-up: six legacy `PytestReturnNotNoneWarning` instances and one
deprecated event-loop warning. They remain visible and were not suppressed.

## Security sweep

- **Secrets:** no runtime or configuration files changed; no new secret-like
  literal was introduced. `gitleaks` remains unavailable in the environment.
- **Injection/path/deserialization:** no production input path, filesystem
  path, subprocess, deserializer, or network behavior changed.
- **Dependencies:** no new dependency. The existing `python -m pip_audit
  --local` blocker remains `383 known vulnerabilities in 77 packages` plus
  local packages unavailable on PyPI; this slice does not change that
  disposition.
- **User-owned files:** no untracked Doctrine file was staged or edited.

**Security verdict:** SIGN-OFF for this test-only slice; repository-wide audit
and full behavioral verification remain open release gates.
**QA verdict:** pass for Slice 25; publish clearance remains open pending the
full repository regression, warning follow-up, dependency-audit disposition,
and independent fresh-context verification.
