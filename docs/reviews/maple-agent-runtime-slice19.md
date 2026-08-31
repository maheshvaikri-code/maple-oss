# Code Review - MAPLE Agent Runtime Slice 19 @ `0648efa`

**Reviewer role:** Code Reviewer · **Date:** 2026-08-24
**Reviewed against:** [brief](../briefs/maple-agent-runtime-release.md),
[ADR-017](../adr/017-bounded-session-store.md), and
[implementation plan](../plans/maple-agent-runtime-release.md)

## Scope

This slice adds a bounded `SessionStore` contract, immutable session/message
values, in-memory and atomic JSON-file implementations, public exports, a
doctor check, documentation, and focused regression tests. It does not bind
sessions to an agent, replay model/tool execution, add a network server, or add
dependencies.

## Findings

| # | Sev | Location | Finding | Suggested fix | Resolution |
|---|---|---|---|---|---|
| 1 | MINOR | `FileSessionStore` | File coordination is process-local; independent processes can race. | Add a lease/CAS backend when multi-process hosting is a requirement. | Explicitly documented in ADR-017 and API reference; accepted for this slice. |
| 2 | MINOR | Session boundary | Stored turns are not automatically replayed into `AutonomousAgent`. | Add agent binding only with an explicit context/version contract. | Explicitly documented as a follow-on; no hidden behavior was introduced. |

## Scope check

The diff matches Slice 19. Inputs are bounded before mutation; JSON parsing
does not deserialize executable objects; file paths are identifier-constrained
and prefix-checked; writes use a same-directory temporary file plus atomic
replacement. No dependency, network, sandbox, or website behavior was added.

## Verification evidence

```text
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'; python -m pytest tests/autonomy/test_sessions.py -q -o addopts=
9 passed, 1 warning in 0.06s

$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'; python -m pytest tests/llm tests/autonomy tests/test_cli.py -q -o addopts=
208 passed, 1 warning in 0.84s

ruff check maple/autonomy/sessions.py tests/autonomy/test_sessions.py
All checks passed!

python -m flake8 maple/autonomy/sessions.py tests/autonomy/test_sessions.py --max-line-length=88 --extend-ignore=E203,W503,W291,W293,E302,E402,F401,F811,F841 --count --statistics
0

python -m maple.cli doctor --json
{"checks": {"core": true, "evaluation": true, "events": true, "execution": true, "interop": true, "retrieval": true, "sessions": true}, "network": false, "ready": true, "status": "SUCCESS", "version": "1.1.3"}

python -m twine check .tmp-maple-session-final\maple_oss-1.1.3-py3-none-any.whl .tmp-maple-session-final\maple_oss-1.1.3.tar.gz
Checking .tmp-maple-session-final\maple_oss-1.1.3-py3-none-any.whl: PASSED
Checking .tmp-maple-session-final\maple_oss-1.1.3.tar.gz: PASSED
```

`gitleaks` is unavailable in this environment. The bounded fallback scan found
no secret pattern in the new implementation or tests. Independent fresh
verifier sessions are unavailable in this tool context, so this is local
review evidence.

## Verdict

- [x] Pass: no open BLOCKER or MAJOR finding.
- [ ] Return to build.
