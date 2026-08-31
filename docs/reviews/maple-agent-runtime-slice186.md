# Slice 186 review — authenticated remote task-queue control plane

**Date:** 2026-08-28
**Reviewer role:** Code Reviewer / Chief Architect local pass
**Implementation commit:** `f4d518f`

## Scope

The review covers the optional `RunServer(task_queue=...)` wiring, the
authenticated `RunClient` task methods, principal scope/target enforcement,
public task-management exports, regression tests, API/README/parity contract,
and release-plan entry. The intended boundary is process-boundary task
coordination, not distributed scheduling or task execution.

## Findings

The transport keeps task admission and lifecycle authority in the selected
`TaskQueue` implementation. Submit, read, claim, complete, and fail operations
have separate `task:*` scopes. Request bodies are read only after route
authorization; payloads, metadata, requirements, results, task types, timeout,
retry, query, and response values remain bounded. Principal capability and
exact worker-agent policies are checked before queue mutation.

Claim and terminal transitions use the queue's existing ownership checks, so a
race between workers returns a typed conflict rather than overwriting an
owner. Queue-owned failures are normalized without exposing durable paths,
filesystem errors, or callback details. The implementation does not infer
worker liveness, automatic retry, handler execution, distributed leases,
queue federation, or exactly-once external effects.

No correctness or security defect was found in the changed boundary. The
repository's broader release remains conditional because the package metadata
is still `1.1.3`, the worktree contains preserved user-owned changes, the
environment-wide dependency audit remains a veto, and independent security
tools/verifier sessions were unavailable.

## Evidence

```text
python -m pytest -q --no-cov tests/autonomy/test_server.py
59 passed in 33.19s

python -m pytest -q --no-cov tests/autonomy tests/task_management
790 passed in 70.73s

python -m pytest -q --no-cov
1746 passed, 1 skipped in 309.92s (0:05:09)

python -m black --check maple/autonomy/server.py maple/task_management/__init__.py tests/autonomy/test_server.py
3 files would be left unchanged.

python -m isort --check-only maple/autonomy/server.py maple/task_management/__init__.py tests/autonomy/test_server.py
exit=0

python -m ruff check tools tests
All checks passed!

python -m compileall -q maple
compileall exit 0

python tools/doctrine_lint.py
doctrine_lint: corpus clean
```

The changed-boundary mypy run reports no new Slice 186 finding; it retains
three existing errors in `maple/autonomy/invocations.py` and
`maple/autonomy/server.py`. `git diff --check` reports only the pre-existing
trailing whitespace in user-modified `demo_package/launch_demos.py`.
Bandit and Gitleaks are unavailable. The environment-wide `pip-audit` result
remains the established release veto: `Found 385 known vulnerabilities in 78
packages`.

The exact clean archive gate at `f4d518f` passed with source archive `869`
entries, `1629 passed, 1 skipped in 253.53s`, wheel `108` entries, sdist `783`
entries, build exit `0`, Twine `PASSED`, isolated install/import exit `0`, and
network-free doctor `ready=true`. The clean wheel SHA-256 was
`dd34ebd91d20e0162fefe5922bab3dff1d586991de478904eea4a0301e9abb1c`.

## Decision

**PASS for the Slice 186 task control-plane boundary and exact clean archive
package gate.** Overall release status remains conditional. No publication,
deployment, cloud action, registry write, or website update was performed.
