# Slice 191 review - owner-safe authenticated remote task start

**Date:** 2026-08-29
**Reviewer role:** Code Reviewer / Chief Architect local pass
**Implementation commit:** `08f71e1`

## Verifier note

This is a local review pass. A fresh independent verifier session could not
be created in the current tool context, so no independent-session approval is
claimed.

## Scope

The review covers the owner-checked `ASSIGNED` to `RUNNING` queue transition,
durable queue persistence, authenticated `task:start` routing, principal
agent/scope policy, timestamp/statistics accounting, regressions, public
documentation, and release evidence. The intended boundary is an explicit
worker lifecycle acknowledgement, not a worker lease or liveness protocol.

## Findings

`TaskQueue.start_task()` validates the actor, task existence, recorded owner,
and exact `ASSIGNED` state while holding the queue lock. It delegates the
accepted transition to the existing status accounting, which records
`started_at`, updates running statistics, and notifies existing callbacks.
`FileTaskQueue` executes the same operation under its atomic fenced durable
read/modify/write wrapper; interrupted running work retains the existing
restart normalization to `QUEUED`.

The server applies authentication, `task:start` scope, target policy, bounded
identifier/body validation, and then the queue-owned state transition. The
route returns the normal bounded task envelope. Repeated, wrong-owner,
queued, terminal, missing, and malformed operations fail closed. No worker
heartbeat, lease, timeout monitor, scheduler, automatic execution, retry,
distributed ownership, or exactly-once side-effect guarantee is introduced.
No correctness or security defect was found in this boundary.

The broader release remains conditional because package metadata is still
`1.1.3`, the worktree contains preserved user-owned changes, the
environment-wide dependency audit remains a veto, and independent verifier
and security tools are unavailable.

## Evidence

```text
focused server + durable queue: 80 passed in 29.76s
autonomy + task-management: 800 passed in 74.75s
full dirty workspace: 1756 passed, 1 skipped in 316.99s (0:05:16)

python -m black --check maple/task_management/task_queue.py maple/task_management/durable_queue.py maple/autonomy/server.py tests/autonomy/test_server.py tests/task_management/test_durable_task_queue.py
5 files would be left unchanged.

python -m isort --check-only maple/task_management/task_queue.py maple/task_management/durable_queue.py maple/autonomy/server.py tests/autonomy/test_server.py tests/task_management/test_durable_task_queue.py
exit=0

python -m ruff check maple/task_management/task_queue.py maple/task_management/durable_queue.py maple/autonomy/server.py tests/autonomy/test_server.py tests/task_management/test_durable_task_queue.py
All checks passed!

python -m compileall -q maple
compileall exit 0
```

The changed-boundary mypy run reports no new Slice191 finding; the existing
three errors in `maple/autonomy/invocations.py` and `maple/autonomy/server.py`
remain documented with the latter at line 6085. The repository Doctrine
lint reports `doctrine_lint: corpus clean`. Bandit and Gitleaks are
unavailable. The environment-wide `pip-audit` result remains the established
release veto: `Found 385 known vulnerabilities in 78 packages`.

The exact clean archive at `08f71e1` passed with `894` archive entries,
`1639 passed, 1 skipped in 259.10s`, build exit `0`, Twine checks, `108` wheel
members, `808` sdist members, isolated install/import, and network-free doctor
with `ready=true`, all eight checks true, `network=false`, and version
`1.1.3`.

Clean artifact SHA-256 values:

```text
wheel dbb34e416254846aaad73d4a6887aef47adbbd00cc46064fe0b72be75cf6d969
sdist a8d77b83c2cd2b122fec9048058d9a22bce6cd11a50fc7f899d87a5ea1d7c0fa
```

Current dirty package evidence is recorded in the release checklist after the
final Slice191 review and QA files are included. No publication was
performed.

## Decision

**PASS for the Slice191 owner-safe explicit task-start boundary and exact
clean archive package gate.** Overall release status remains conditional. No
publication, deployment, cloud action, registry write, or website update was
performed.
