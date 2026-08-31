# Code Review - MAPLE Agent Runtime Slice 16 @ working tree

**Reviewer role:** Code Reviewer · **Date:** 2026-08-24
**Reviewed against:** [brief](../briefs/maple-agent-runtime-release.md),
[ADR-014](../adr/014-durable-tool-approval.md), and
[implementation plan](../plans/maple-agent-runtime-release.md)

## Scope

This slice adds bounded in-memory and atomic JSON-file approval stores,
operator decision transitions, one-time consume transitions, and autonomous
agent integration for pending required-tool actions. Callback approval remains
backward compatible and takes precedence. The slice does not claim durable
ReAct conversation replay, cross-process CAS/leases, notifications, or a hard
sandbox.

## Findings

| # | Sev | Location | Finding | Suggested fix | Resolution |
|---|---|---|---|---|---|
| 1 | MINOR | `FileApprovalStore` | Atomic local JSON persistence does not coordinate simultaneous consumers in separate processes. | Add a deployment-specific lease/CAS adapter before multi-process use. | Documented in ADR-014 and API reference; accepted for the dependency-free local store. |
| 2 | MINOR | Approval arguments | Persisted arguments can contain application-sensitive data. | Protect the approval directory and define retention at the host boundary. | Documented in ADR-014 and API reference; no logging or external transmission added. |

## Scope check

The diff matches Slice 16. It adds no dependency, cloud call, website change,
publication action, or license change. Request data is bounded and JSON-only;
missing stores, malformed records, unresolved decisions, store failures, and
replay attempts fail closed without invoking the handler.

## Verification evidence

```text
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'; python -m pytest tests/autonomy/test_approval.py tests/autonomy/test_agent.py -q -o addopts=
21 passed, 1 warning in 0.05s

$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'; python -m pytest tests/llm tests/autonomy tests/test_cli.py -q -o addopts=
192 passed, 1 warning in 0.87s

ruff check maple/autonomy/approval.py maple/autonomy/agent.py tests/autonomy/test_approval.py tests/autonomy/test_agent.py
All checks passed!

python -m flake8 maple/autonomy/approval.py maple/autonomy/agent.py tests/autonomy/test_approval.py tests/autonomy/test_agent.py --max-line-length=88 --extend-ignore=E203,W503,W291,W293,E302,E402,F401,F811,F841 --count --statistics
0

python -m compileall -q maple
compileall exit code: 0

python -m maple.cli doctor --json
{"checks": {"core": true, "evaluation": true, "events": true, "execution": true, "interop": true, "retrieval": true}, "network": false, "ready": true, "status": "SUCCESS", "version": "1.1.3"}

python -m twine check '.tmp-maple-approval-final\*'
Checking .tmp-maple-approval-final\maple_oss-1.1.3-py3-none-any.whl: PASSED
Checking .tmp-maple-approval-final\maple_oss-1.1.3.tar.gz: PASSED
```

The pytest warning is the existing `asyncio_mode` configuration warning when
plugin autoload is disabled. Independent fresh-context verifier sessions are
not available in this tool context, so this is local review evidence only.

## Verdict

- [x] Pass: no open BLOCKER or MAJOR finding.
- [ ] Return to build.
