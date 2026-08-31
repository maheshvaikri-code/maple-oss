# Code Review - native autonomous-agent remote transport adapter

**Review basis:** `c94328e`, `e1812f6`, `b3d8f74`, `abf02d6`
**Brief:** `docs/briefs/maple-agent-runtime-slice169.md`
**ADR:** `docs/adr/114-native-agent-remote-transport-adapter.md`
**Date:** 2026-08-28
**Role:** Code Reviewer

## Decision

Pass for Slice 169.

## Review coverage

- Reviewed `AutonomousAgentRemoteAdapter` as an isolated boundary adapter over
  `AgentRegistry`; it does not couple `RunServer` to the autonomous runtime.
- Verified constructor validation for bounded agent identity, the caller-owned
  `AgentRunStore`, and required native methods, followed by public store
  binding through `set_run_store`.
- Verified native start and resume callback mapping preserves the requested run
  identity, accepts only completed/paused goals, bounds JSON results, and
  converts failed/cancelled goals to generic terminal errors.
- Verified native callback errors and exceptions do not copy provider details
  into the remote error response; cancellation is registered only when the host
  supplies an explicit callback.
- Reviewed authenticated `RunServer`/`RunClient` integration tests, exports,
  API docs, README, changelog, parity ledger, slice plan, and release plan.

## Findings

No correctness, compatibility, or Slice-169-specific security blocker was
found.

The adapter deliberately does not synthesize checkpoints, transfer native
checkpoint contents, infer cancellation behavior, retry remote work, select a
remote worker, schedule work, push notifications, federate identity, or claim
exactly-once side effects. The native agent and host remain the owners of
checkpoint persistence and cancellation policy.

## Verification

```text
python -m pytest tests/autonomy/test_agent_transport.py tests/autonomy/test_server.py tests/autonomy/test_tools.py -q --no-cov
90 passed in 20.12s

python -m pytest <tracked Python test files> -q --no-cov
1528 passed, 1 skipped in 215.55s

python -m ruff check maple tests
All checks passed!

python -m mypy --follow-imports=skip maple/autonomy/agent_transport.py maple/autonomy/server.py maple/autonomy/__init__.py maple/__init__.py
Success: no issues found in 4 source files

slice169_secret_scan=passed
slice169_danger_scan=passed
```

The committed feature diff contains no publication, deployment, cloud,
registry, or website action. This environment does not provide a separate
fresh-session verifier, so independent fresh-session review remains a
release-governance follow-up rather than being claimed here.
