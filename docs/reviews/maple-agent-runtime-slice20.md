# Code Review - MAPLE Agent Runtime Slice 20 @ `7665eaf`

**Reviewer role:** Code Reviewer · **Date:** 2026-08-24
**Reviewed against:** [brief](../briefs/maple-agent-runtime-release.md),
[ADR-018](../adr/018-loopback-workflow-run-server.md), and
[implementation plan](../plans/maple-agent-runtime-release.md)

## Scope

This slice adds a bounded `WorkflowRegistry`, a loopback-only stdlib
`RunServer`, health/run/resume/inspect routes, lifecycle tests, public exports,
doctor coverage, and API/release documentation. It reuses the existing
workflow/checkpoint boundary and adds no remote deployment, authentication,
TLS, arbitrary workflow registration, or dependency.

## Findings

| # | Sev | Location | Finding | Suggested fix | Resolution |
|---|---|---|---|---|---|
| 1 | MINOR | `RunServer` | The surface is intentionally unauthenticated and local-only. | Add an explicit auth/TLS/remote ADR before exposing it beyond loopback. | Documented in ADR-018 and API reference; accepted for local parity. |
| 2 | MINOR | HTTP transport | This slice returns complete JSON responses; streaming/SSE/WebSocket is not included. | Add streaming only after a bounded event-wire contract and cancellation tests exist. | Explicitly deferred; existing in-process event/LLM streams remain unchanged. |

## Scope check

The diff matches Slice 20. Registered workflows are host-owned; HTTP cannot
register executable handlers. Request bodies, path lengths, response sizes,
workflow state, and resume values are bounded at their respective boundaries.
The server thread is explicitly owned and shut down by `close()`/context exit.

## Verification evidence

```text
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'; python -m pytest tests/autonomy/test_server.py -q -o addopts=
4 passed, 1 warning in 2.08s

$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'; python -m pytest tests/llm tests/autonomy tests/test_cli.py -q -o addopts=
212 passed, 1 warning in 3.03s

ruff check maple/autonomy/server.py tests/autonomy/test_server.py
All checks passed!

python -m flake8 maple/autonomy/server.py tests/autonomy/test_server.py maple/cli.py tests/test_cli.py --max-line-length=88 --extend-ignore=E203,W503,W291,W293,E302,E402,F401,F811,F841 --count --statistics
0

python -m maple.cli doctor --json
{"checks": {"core": true, "evaluation": true, "events": true, "execution": true, "interop": true, "retrieval": true, "server": true, "sessions": true}, "network": false, "ready": true, "status": "SUCCESS", "version": "1.1.3"}

python -m twine check .tmp-maple-server-final\maple_oss-1.1.3-py3-none-any.whl .tmp-maple-server-final\maple_oss-1.1.3.tar.gz
Checking .tmp-maple-server-final\maple_oss-1.1.3-py3-none-any.whl: PASSED
Checking .tmp-maple-server-final\maple_oss-1.1.3.tar.gz: PASSED
```

`gitleaks` is unavailable in this environment. The fallback scan found no
secret pattern or dangerous execution construct in the new implementation or
tests. Independent fresh verifier sessions are unavailable in this tool
context, so this is local review evidence.

## Verdict

- [x] Pass: no open BLOCKER or MAJOR finding.
- [ ] Return to build.
