# QA + Security Report - MAPLE agent runtime slice 26 @ `948b9ea`

**QA Engineer** · **Security Reviewer** · **Date:** 2026-08-25
**Build under test:** commit `948b9ea` (`fix(test): fail legacy checks instead of returning booleans`)

## Acceptance criteria verification

| # | Criterion | How executed | Evidence | Pass |
|---|-----------|--------------|----------|------|
| 1 | Legacy basic tests fail closed under pytest instead of returning ignored booleans. | Ran the pytest module and standalone script. | `22 passed in 0.26s`; standalone output reports `6 passed, 0 failed`. | PASS |
| 2 | S2 async test cleanup removes the deprecated event-loop lookup. | Ran the S2 adapter test module. | Targeted module passes with no warning output. | PASS |
| 3 | Repository quality gates remain green. | Ran Ruff and test compilation. | `All checks passed!`; `COMPILE_EXIT=0`. | PASS |

## Adversarial & edge matrix

| Input/scenario | Expected | Observed | Pass |
|----------------|----------|----------|------|
| Basic import failure | Exception reaches pytest/standalone failure path | `test_imports` no longer returns a silently ignored `False` | PASS |
| Basic functional assertion failure | Exception reaches caller | All six checks use ordinary assertions and re-raise caught exceptions | PASS |
| Standalone success path | Counts each completed check | `6 passed, 0 failed` | PASS |
| S2 empty-cache async read | Same `Result` assertions without deprecated loop lookup | Targeted adapter tests pass | PASS |

## Regression

```text
python -m pytest tests/test_basic.py tests/adapters/test_s2_adapter.py -q -o addopts=
22 passed in 0.26s

python tests/test_basic.py
[STATS] Test Results: 6 passed, 0 failed
[SUCCESS] All tests passed! MAPLE is working correctly.

python -m ruff check tools tests
All checks passed!

python -m compileall -q tests
COMPILE_EXIT=0
```

The full repository behavioral verifier remains incomplete; the previous
bounded run was stopped before its unittest summary after the lint gate was
separately cleared in Slice 25. This slice does not claim a full-suite pass.

## Bugs found

| # | Repro steps | Severity | Fixed @ | Re-verified | Regression test |
|---|-------------|----------|---------|-------------|-----------------|
| 1 | Run pytest on `tests/test_basic.py`; pytest emitted six `PytestReturnNotNoneWarning` warnings and would treat returned `False` as non-failing. | MAJOR | `948b9ea` | `22 passed`, no targeted warning output | `tests/test_basic.py` six checks plus standalone runner |
| 2 | Run the S2 empty-cache async test; `asyncio.get_event_loop()` emitted a deprecation warning. | MINOR | `948b9ea` | `22 passed`, no targeted warning output | `tests/adapters/test_s2_adapter.py` async cache tests |

## Security sweep

- **Secrets:** no runtime/configuration files changed; no new secret-like
  literal introduced. `gitleaks` remains unavailable.
- **Injection/path/deserialization:** no production input, filesystem,
  subprocess, deserialization, or network behavior changed.
- **Dependencies:** no new dependency. The existing shared-environment
  `pip-audit` blocker remains `383 known vulnerabilities in 77 packages`
  plus local packages unavailable on PyPI.

**Security verdict:** SIGN-OFF for this test-only slice; dependency audit and
independent fresh-context verification remain open release gates.
**QA verdict:** pass for Slice 26; publish clearance remains open pending the
full repository regression, dependency-audit disposition, and independent
fresh-context verification.
