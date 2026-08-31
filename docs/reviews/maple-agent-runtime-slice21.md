# Code Review - MAPLE Agent Runtime Slice 21 @ `0b794ba`

**Reviewer role:** Code Reviewer · **Date:** 2026-08-24  
**Reviewed against:** [ADR-019](../adr/019-session-aware-agent-turns.md) and
[implementation plan](../plans/maple-agent-runtime-release.md)

## Scope

This slice binds `AutonomousAgent` sync and async turns to the existing
bounded `SessionStore` through an explicit `session_id`. It adds CAS-protected
user-turn persistence, user/assistant-only prompt replay, explicit
post-execution persistence errors, tests, and public documentation. It adds no
automatic persistence, trace replay, tool replay, compaction, authentication,
new dependency, or external publication.

## Findings

| # | Sev | Location | Finding | Suggested fix | Resolution |
|---|---|---|---|---|---|
| 1 | [MAJOR] | `maple/autonomy/agent.py` session-store boundary | A host-provided store that raised an exception could escape the `Result` contract before the LLM, or convert a post-run write failure into a generic goal error. | Contain store exceptions and return a typed failure; preserve the completed `Goal` and expose the failure through `session_error`. | Fixed before commit `0b794ba`; regression tests added. |

## Scope check

The diff matches Slice 21. Session use is opt-in and the no-session path is
unchanged. The current user message is appended before model execution with
the loaded version as `expected_version`; concurrent stale writers fail before
the model is called. Stored `system` and `tool` messages are retained as data
but are not promoted into the prompt. Results are bounded by the existing
session store boundary and persistence errors are visible to callers.

## Verification evidence

```text
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'; python -m pytest tests/autonomy/test_agent_sessions.py -q -o addopts=
7 passed, 1 warning in 0.04s

$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'; python -m pytest tests/llm tests/autonomy tests/test_cli.py -q -o addopts=
219 passed, 1 warning in 3.07s

python -m ruff check maple/autonomy/agent.py tests/autonomy/test_agent_sessions.py --output-format concise
All checks passed!

python -m flake8 maple/autonomy/agent.py tests/autonomy/test_agent_sessions.py --max-line-length=88 --extend-ignore=E203,W503,W291,W293,E302,E402,F401,F811,F841 --count --statistics
0

python -m compileall -q maple
COMPILE_EXIT=0

python -m maple.cli doctor --json
{"checks": {"core": true, "evaluation": true, "events": true, "execution": true, "interop": true, "retrieval": true, "server": true, "sessions": true}, "network": false, "ready": true, "status": "SUCCESS", "version": "1.1.3"}
```

Independent fresh verifier sessions were unavailable in this tool context;
this is the local G4 review record.

## Verdict

- [x] Pass: no open BLOCKER or MAJOR finding.
- [ ] Return to build.
