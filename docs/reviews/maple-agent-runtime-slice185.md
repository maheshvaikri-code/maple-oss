# Slice 185 review — bounded durable local task queue

**Date:** 2026-08-28
**Reviewer role:** Code Reviewer / Chief Architect local pass
**Implementation commit:** pending evidence commit

## Scope

The review covers `FileTaskQueue`, its public package export, regression tests,
the API/README/parity contract, and the release-plan entry. The intended
boundary is local durable task admission, not a distributed queue or hosted
scheduler.

## Findings

The implementation uses a caller-selected canonical JSON state file and the
existing `FileLeaseManager` for a short-lived cross-process read/modify/write
fence. State is written to a same-directory temporary file, flushed and
`fsync`ed, and atomically replaced. The state is bounded by task count,
per-task bytes, whole-file bytes, JSON depth/items, text fields, retry values,
and error bytes.

Startup hydration is the only point that normalizes interrupted
`ASSIGNED`/`RUNNING`/`PENDING` records to `QUEUED`; ordinary operations preserve
valid assignments. Terminal records remain durable because the inherited
background cleanup thread is intentionally not started. Persistence failures
restore the pre-operation in-memory state, and malformed state or fence
contention fails closed without replacing the state file.

The queue retains `TaskQueue`/`TaskScheduler` method names and `Result` return
shapes. The review found no correctness or security defect in the changed
boundary. The explicit non-claims are documented: no distributed worker lease,
automatic retry, hosted scheduling, remote queue, handler replay, or
exactly-once external effect guarantee.

## Evidence

```text
python -m pytest -q --no-cov tests/task_management/test_durable_task_queue.py
11 passed in 0.63s

python -m pytest -q --no-cov tests/task_management
178 passed in 22.75s

python -m pytest -q --no-cov
1743 passed, 1 skipped in 314.00s (0:05:14)

python -m black --check maple/
101 files would be left unchanged.

python -m isort --check-only maple/task_management/durable_queue.py maple/task_management/__init__.py
exit=0

python -m ruff check tools tests
All checks passed!

python -m compileall -q maple
compileall exit 0

python tools/doctrine_lint.py
doctrine_lint: corpus clean
```

The changed module adds no mypy finding; the targeted command still reports
three pre-existing findings in `maple/autonomy/invocations.py` and
`maple/autonomy/server.py`. The repository-wide isort check still reports
pre-existing drift in `maple/autonomy/orchestrator.py`, `maple/llm/provider.py`,
`maple/llm/__init__.py`, and `maple/resources/__init__.py`. Bandit and Gitleaks
are unavailable in this environment. The environment-wide pip-audit remains
a release veto with 385 known vulnerabilities in 78 packages.

## Decision

**PASS for the bounded local durable queue boundary.** Clean-archive package
evidence is a separate release gate. No publication, deployment, cloud action,
registry write, or website update was performed.
