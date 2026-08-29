# Slice 190 review - authenticated remote task queue statistics

**Date:** 2026-08-29
**Reviewer role:** Code Reviewer / Chief Architect local pass
**Implementation commit:** `1cf3081`

## Verifier note

This is a local review pass. A fresh independent verifier session could not
be created in the current tool context, so no independent-session approval is
claimed.

## Scope

The review covers the fixed queue-statistics serializer, authenticated
`GET /v1/tasks/stats` routing, `task:read` authorization, client coverage,
malformed/non-finite value handling, in-memory and durable queue compatibility,
public documentation, and release evidence. The intended boundary is bounded
host-local telemetry, not hosted monitoring or distributed aggregation.

## Findings

The route is additive and is dispatched only after authentication. It returns
only the fixed `QueueStats` counters and finite timing/throughput measurements;
task payloads, results, queue internals, and arbitrary extra fields are not
serialized. Malformed, non-finite, negative, non-integer, oversized, or
exceptional queue statistics fail closed as `TASK_QUEUE_UNAVAILABLE`.

The client method uses the existing `task:read` scope. The queue is read
through `get_queue_stats()` without changing task state, and both in-memory
and file-backed queues remain compatible. Existing task inspection and task
mutation routes are not changed. No dashboards, alerts, hosted exporters,
cross-process aggregation, scheduling, leases, or worker lifecycle semantics
are introduced. No correctness or security defect was found in this boundary.

The broader release remains conditional because package metadata is still
`1.1.3`, the worktree contains preserved user-owned changes, the
environment-wide dependency audit remains a veto, and independent verifier
and security tools are unavailable.

## Evidence

```text
focused server: 65 passed in 28.48s
autonomy + task-management: 798 passed in 73.48s
full dirty workspace: 1754 passed, 1 skipped in 321.08s (0:05:21)

python -m black --check maple/autonomy/server.py tests/autonomy/test_server.py
2 files would be left unchanged.

python -m isort --check-only maple/autonomy/server.py tests/autonomy/test_server.py
exit=0

python -m ruff check tools tests
All checks passed!

python -m compileall -q maple
compileall exit 0
```

The changed-boundary mypy run reports no new Slice 190 finding; it retains
three existing errors in `maple/autonomy/invocations.py` and
`maple/autonomy/server.py` (the latter is reported at line 6057). The
repository Doctrine lint reports `doctrine_lint: corpus clean`. Bandit and
Gitleaks are unavailable. The environment-wide `pip-audit` result remains the
established release veto: `Found 385 known vulnerabilities in 78 packages`.

The exact clean archive at `1cf3081` passed with `889` archive entries,
`1637 passed, 1 skipped in 260.03s`, build exit `0`, Twine checks, `108` wheel
members, `803` sdist members, isolated install/import, and network-free doctor
with `ready=true`, all eight checks true, `network=false`, and version
`1.1.3`.

Clean artifact SHA-256 values:

```text
wheel 790fe7f825ea28e00cc6e3c9a5a100db676779c034ec04ecfdf28915213725bc
sdist 19e7afcd1487fc4cb179a22e97ac2680a3172a86bed117a3a060f9c5453d136f
```

Current dirty package evidence is recorded in the release checklist after the
final documentation files are included. No publication was performed.

## Decision

**PASS for the Slice 190 read-only remote task-statistics boundary and exact
clean archive package gate.** Overall release status remains conditional. No
publication, deployment, cloud action, registry write, or website update was
performed.
