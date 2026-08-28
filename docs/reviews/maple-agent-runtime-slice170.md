# Code Review - bounded agent capability discovery and routing

**Review basis:** `19390dd`, `d3c720c`
**Brief:** `docs/briefs/maple-agent-runtime-slice170.md`
**ADR:** `docs/adr/115-bounded-agent-capability-routing.md`
**Date:** 2026-08-28
**Role:** Code Reviewer

## Decision

Pass for Slice 170.

## Review coverage

- Reviewed the additive `AgentDescriptor` and capability registration path for
  bounded labels, uniqueness, deterministic ordering, and legacy registration
  compatibility.
- Verified `AgentRegistry.route(...)` performs exact capability matching,
  chooses the lexicographically first agent, and delegates to the existing
  task/context/run validation and `AgentRun` normalizer.
- Verified `GET /v1/agents` exposes metadata only and `POST
  /v1/agent-routes/runs` uses the existing bearer authentication and
  `agent:invoke` scope; no handler or checkpoint data is serialized.
- Verified raw client compatibility, typed listing/route validation, selected
  run identity checks, missing-registry/no-match behavior, and native-adapter
  capability forwarding.
- Reviewed public exports, API documentation, parity wording, changelog, and
  explicit no-retry/no-failover/no-scheduler/no-exactly-once boundaries.

## Findings

No correctness, compatibility, or Slice-170-specific security blocker was
found. The route is intentionally deterministic selection rather than health,
capacity, fairness, failover, or distributed scheduling. Those concerns remain
separate architecture and identity boundaries.

The repository does not provide a separate fresh-session verifier in this
environment; that independent verification remains a release-governance
follow-up and is not claimed here.

## Verification

```text
python -m pytest tests/autonomy/test_server.py tests/autonomy/test_agent_transport.py -q --no-cov
56 passed in 21.28s

python -m pytest -q --no-cov
1649 passed, 1 skipped in 267.21s

python -m ruff check maple/autonomy/server.py maple/autonomy/agent_transport.py maple/autonomy/__init__.py maple/__init__.py tests/autonomy/test_server.py tests/autonomy/test_agent_transport.py
All checks passed!

python -m mypy --follow-imports=skip maple/autonomy/server.py maple/autonomy/agent_transport.py maple/autonomy/__init__.py maple/__init__.py
Success: no issues found in 4 source files

slice170_secret_scan=passed
slice170_danger_scan=passed
```
