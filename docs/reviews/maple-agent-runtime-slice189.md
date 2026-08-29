# Slice 189 review - owner-safe remote task retry

**Date:** 2026-08-29
**Reviewer role:** Code Reviewer / Chief Architect local pass
**Implementation commit:** `13c5956`

## Verifier note

This is a local review pass. A fresh independent verifier session could not
be created in the current tool context, so no independent-session approval is
claimed.

## Scope

The review covers owner-aware in-memory and durable requeue behavior, the
authenticated retry route and client method, scope and principal policy,
stable queue error normalization, regressions, public documentation, and
release evidence. The intended boundary is explicit caller-driven retry, not
automatic scheduling or distributed coordination.

## Findings

The route is additive and uses a dedicated `task:retry` scope. The server
validates the task identifier and assigned agent, applies principal target
policy before queue mutation, accepts only the assigned-agent field, and
returns the requeued task envelope without exposing queue internals.

The owner-aware queue path checks failed state, recorded ownership, retry
count, and capacity while holding the queue mutation lock. Successful requeue
clears ownership and increments the bounded retry count. `FileTaskQueue`
persists the same transition through its durable fencing wrapper. The legacy
no-owner local `requeue_task(task_id)` path remains available for compatibility.

Terminal/non-failed tasks, missing tasks, malformed bodies, mismatched owners,
and exhausted retry counts fail closed. The corrected error mapping reports
retry exhaustion as `TASK_CONFLICT`. The operation does not automatically
retry work, run handlers, select workers, revoke leases, federate queues, or
claim exactly-once external effects. No correctness or security defect was
found in the changed boundary.

The broader release remains conditional because package metadata is still
`1.1.3`, the worktree contains preserved user-owned changes, the
environment-wide dependency audit remains a veto, and independent verifier
and security tools are unavailable.

## Evidence

```text
python -m pytest -q --no-cov tests/autonomy/test_server.py tests/task_management/test_durable_task_queue.py tests/task_management/test_task_submission.py
97 passed in 27.88s

python -m pytest -q --no-cov tests/autonomy tests/task_management
795 passed in 72.22s

python -m pytest -q --no-cov
1751 passed, 1 skipped in 312.60s (0:05:12)

python -m black --check maple/task_management/task_queue.py maple/task_management/durable_queue.py maple/autonomy/server.py tests/autonomy/test_server.py tests/task_management/test_durable_task_queue.py
5 files would be left unchanged.

python -m isort --check-only maple/task_management/task_queue.py maple/task_management/durable_queue.py maple/autonomy/server.py tests/autonomy/test_server.py tests/task_management/test_durable_task_queue.py
exit=0

python -m ruff check tools tests
All checks passed!

python -m compileall -q maple
compileall exit 0
```

The changed-boundary mypy run reports no new Slice 189 finding; it retains
three existing errors in `maple/autonomy/invocations.py` and
`maple/autonomy/server.py` (the latter is reported at line 5977). `git diff
--check` reports only the pre-existing
trailing whitespace in user-modified `demo_package/launch_demos.py`.
Bandit and Gitleaks are unavailable. The environment-wide `pip-audit` result
remains the established release veto: `Found 385 known vulnerabilities in 78
packages`.

The exact clean archive at `13c5956` passed with `884` archive entries,
`1634 passed, 1 skipped in 260.53s`, build exit `0`, Twine checks, `108` wheel
members, `798` sdist members, isolated install/import, and doctor with
`ready=true`, all eight checks true, `network=false`, and version `1.1.3`.

The current dirty source tree also built with exit `0`, passed Twine, isolated
install/import, and network-free doctor; its sdist contains `807` members.

Clean artifact SHA-256 values:

```text
wheel e171da9cf000dad3e6e79dd841159b974374eeb3a8d492305f7e2ed17e6c54ea
sdist c5f78718bc94cb84166e33bb56253e6737696db5bc9ce0bfeae3358ce1c8c8c2
```

## Decision

**PASS for the Slice 189 owner-safe explicit retry boundary and exact clean
archive package gate.** Overall release status remains conditional. No
publication, deployment, cloud action, registry write, or website update was
performed.
