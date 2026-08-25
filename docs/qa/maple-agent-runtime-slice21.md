# QA + Security - MAPLE Agent Runtime Slice 21 @ `0b794ba`

**QA Engineer · Security Reviewer · Date:** 2026-08-24  
**Build under test:** exact commit `0b794ba`; package version `1.1.3`

## Acceptance criteria verification

| # | Criterion | How executed | Evidence | Pass |
|---|---|---|---|---|
| 1 | Sync and async agents can opt into bounded multi-turn sessions. | Seven focused tests exercise sync turns, async turns, and persisted user/assistant messages. | `7 passed`; combined gate `219 passed`. | PASS |
| 2 | Current user turns are persisted before model execution with CAS protection. | Missing-store and raising-store tests assert typed failure and zero LLM calls; existing session suite covers version conflicts. | `SESSION_STORE_UNAVAILABLE` / `SESSION_STORE_ERROR`; `tests/autonomy/test_sessions.py` included in combined gate. | PASS |
| 3 | Stored system/tool data is not replayed into the model prompt. | Preloaded session contains user, assistant, system, and tool messages; captured model prompt is checked by role and content. | Only agent system prompt plus user/assistant history is observed; hostile system/tool content is absent. | PASS |
| 4 | Post-execution persistence failures remain visible without hiding the execution result. | Store quota and raising-store tests force assistant append failures after the model returns. | `Goal` remains successful/completed and exposes `SESSION_MESSAGE_LIMIT` or `SESSION_STORE_ERROR` in `session_error`. | PASS |
| 5 | Public/runtime release surfaces remain valid. | Ruff, Flake8, compileall, doctor, wheel/sdist build, Twine, and installed-wheel smoke. | Changed surface clean; compile/doctor exit 0; Twine `PASSED`; installed wheel doctor ready. | PASS |

## Adversarial & edge matrix

| Input/scenario | Expected | Observed | Pass |
|---|---|---|---|
| No configured store with `session_id` | Fail before LLM | `SESSION_STORE_UNAVAILABLE`; provider call list empty | PASS |
| Host store raises during load or result append | Typed fail-closed boundary; post-run error remains on goal | `SESSION_STORE_ERROR`; no pre-call model call; post-run `Goal.session_error` | PASS |
| Store message quota at limit | User append can succeed; assistant write failure is explicit | `SESSION_MESSAGE_LIMIT` on `Goal.session_error` | PASS |
| Stored `system`/`tool` messages | Never replay as trusted prompt instructions | Captured prompt excludes both contents and roles | PASS |
| Existing session version conflict | Reject stale mutation | Covered by bounded session-store regression suite in combined gate | PASS |
| Async execution | Same persistence/filter contract without blocking event loop | Async focused test passes with executor-backed store operations | PASS |

## Regression

```text
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'; python -m pytest tests/autonomy/test_agent_sessions.py -q -o addopts=
7 passed, 1 warning in 0.04s

$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'; python -m pytest tests/llm tests/autonomy tests/test_cli.py -q -o addopts=
219 passed, 1 warning in 3.07s

python -m compileall -q maple
COMPILE_EXIT=0

python -m twine check .tmp-maple-slice21-final2\maple_oss-1.1.3-py3-none-any.whl .tmp-maple-slice21-final2\maple_oss-1.1.3.tar.gz
Checking ...maple_oss-1.1.3-py3-none-any.whl: PASSED
Checking ...maple_oss-1.1.3.tar.gz: PASSED

Installed wheel smoke, run outside the source tree:
{"checks": {"core": true, "evaluation": true, "events": true, "execution": true, "interop": true, "retrieval": true, "server": true, "sessions": true}, "network": false, "ready": true, "status": "SUCCESS", "version": "1.1.3"}
```

The pytest warning is the existing `asyncio_mode` configuration warning when
plugin autoload is disabled. A no-index dependency installation was also
attempted and could not resolve the existing `asyncio-mqtt>=0.11.0` package;
the installed-wheel smoke therefore used `--no-deps` and verified MAPLE from
outside the checkout. This remains a release-environment dependency gate.

## Bugs found

| # | Repro steps | Severity | Fixed @ | Re-verified | Regression test |
|---|---|---|---|---|---|
| 1 | Configure a host store whose `load` or `append` raises during a session turn. | MAJOR | `0b794ba` | Seven focused and 219 combined tests pass. | `test_session_store_exception_fails_closed_before_llm`; `test_session_store_exception_after_execution_is_exposed_on_goal` |

## Security sweep

- **Secrets:** `gitleaks` is unavailable. The fallback scan found no
  credential literals in the new agent/session implementation, tests, or ADR;
  broader repository matches are existing placeholders/documentation.
- **Input/path/deserialization:** session IDs and message fields are bounded
  and JSON-validated by `SessionStore`; agent binding does not execute stored
  values, and system/tool messages are not replayed into prompts.
- **Dependencies:** Slice 21 adds no dependency and uses the existing session
  store and standard-library executor. `python -m pip_audit --local` reported
  `383` known vulnerabilities across `77` shared-interpreter packages, plus
  packages unavailable on PyPI; these are pre-existing environment findings,
  not introduced by this slice, and keep the repository release gate open.
- **Dangerous constructs:** no `pickle`, `eval`, `exec`, shell execution,
  network listener, or new filesystem surface was added by this slice.
- **Bounds/fail-closed:** pre-call persistence failures stop model execution;
  quotas remain enforced by the store; post-call failures are returned on the
  `Goal` rather than hidden.

**Security verdict:** SIGN-OFF for this changed feature boundary; repository
dependency audit and release authorization remain open.  
**QA verdict:** CONDITIONAL PASS for Slice 21; full repository regression,
repository-wide lint, independent fresh-context verification, shared
dependency remediation, and external publication remain open release gates.
