# Code Review - typed remote agent-run lifecycle

**Review basis:** `bfbeef8`, `2726fab`, and `77b2d2b`
**Brief:** `docs/briefs/maple-agent-runtime-slice168.md`
**ADR:** `docs/adr/113-typed-remote-agent-lifecycle.md`
**Date:** 2026-08-28
**Role:** Code Reviewer

## Decision

Pass for Slice 168.

## Review coverage

- Reviewed the shared remote run-envelope normalizer and the additive
  `RunClient.run_agent_typed(...)`, `resume_agent_run_typed(...)`, and
  `cancel_agent_run_typed(...)` methods.
- Verified that the typed methods delegate to the existing authenticated raw
  methods, preserve the wire contract, enforce requested agent/run identity,
  reuse bounded `AgentRun` normalization, and reject an invalid cancel status.
- Verified that malformed responses return generic `AGENT_RESPONSE_INVALID`
  errors without returning the remote raw result or error payload.
- Reviewed the two new regression tests, API reference, README, changelog,
  parity wording, slice plan, and release-plan entry.

## Findings

No correctness, compatibility, or Slice-168-specific security blocker was
found.

The implementation is response normalization only. It does not add remote
checkpoint persistence, automatic retries, scheduling, push delivery,
identity federation, or exactly-once side-effect semantics. Valid failed and
cancelled remote runs remain typed `AgentRun` data so callers can make an
explicit lifecycle decision.

## Verification

```text
python -m pytest tests/autonomy/test_tools.py tests/autonomy/test_server.py -q --no-cov
85 passed in 19.78s

python -m pytest <tracked Python test files> -q --no-cov
1523 passed, 1 skipped in 224.57s

python -m ruff check maple tests
All checks passed!

python -m mypy --follow-imports=skip maple/autonomy/server.py
Success: no issues found in 1 source file

slice168_secret_scan=passed
slice168_danger_scan=passed
```

The committed feature diff contains no publication, deployment, cloud,
registry, or website action. This environment does not provide a separate
fresh-session verifier, so independent fresh-session review remains a
release-governance follow-up rather than being claimed here.
