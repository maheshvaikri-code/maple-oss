# Slice 187 review - non-blocking remote claim-next

**Date:** 2026-08-28
**Reviewer role:** Code Reviewer / Chief Architect local pass
**Implementation commit:** `2aabca9`

## Verifier note

This is a local review pass. A fresh independent verifier session could not
be created in the current tool context, so no independent-session approval is
claimed.

## Scope

The review covers the authenticated `claim-next` route and client method,
scope mapping, principal target policy, bounded capability handling,
deterministic candidate selection, queue ownership transition, regressions,
public documentation, and release evidence. The intended boundary is bounded
remote worker ergonomics, not distributed scheduling or task execution.

## Findings

The route is additive and uses the existing `task:claim` authorization scope.
Route authorization occurs before request-body handling, and principal
agent/capability allowlists are checked before queue inspection or mutation.
The request accepts only the assigned agent and a bounded capability list.

Candidate reads are capped by the existing remote task-list bound. Selection
is deterministic by priority, creation time, and task ID. Requirement matching
is exact against the caller's declared capabilities. Each ownership transition
is delegated to `TaskQueue.assign_task()`, so an ownership conflict cannot
overwrite another worker; bounded conflict/not-found races advance to the next
candidate.

The operation does not start or stop the queue, wait in a consumer loop, or
introduce worker liveness, leases, retries, fairness, federation, handler
execution, or exactly-once external effects. No correctness or security defect
was found in the changed boundary.

The broader release remains conditional because package metadata is still
`1.1.3`, the worktree contains preserved user-owned changes, the
environment-wide dependency audit remains a veto, and independent verifier
and security tools are unavailable.

## Evidence

```text
python -m pytest -q --no-cov tests/autonomy/test_server.py
60 passed in 25.97s

python -m pytest -q --no-cov tests/autonomy tests/task_management
791 passed in 71.78s

python -m pytest -q --no-cov
1747 passed, 1 skipped in 309.42s (0:05:09)

python -m black --check maple/autonomy/server.py tests/autonomy/test_server.py
2 files would be left unchanged.

python -m isort --check-only maple/autonomy/server.py tests/autonomy/test_server.py
exit=0

python -m ruff check tools tests
All checks passed!

python -m compileall -q maple
compileall exit 0
```

The changed-boundary mypy run reports no new Slice 187 finding; it retains
three existing errors in `maple/autonomy/invocations.py` and
`maple/autonomy/server.py`. `git diff --check` reports only the pre-existing
trailing whitespace in user-modified `demo_package/launch_demos.py`.
Bandit and Gitleaks are unavailable. The environment-wide `pip-audit` result
remains the established release veto: `Found 385 known vulnerabilities in 78
packages`.

The current dirty package smoke passed build exit `0`, Twine checks,
no-dependency wheel install/import, and network-free doctor; its sdist has
`797` members. The exact clean archive at `2aabca9` passed with `874` archive
entries, `1630 passed, 1 skipped in 254.93s`, build exit `0`, Twine checks,
`108` wheel members, `788` sdist members, isolated install/import, and doctor
with `ready=true`, all eight checks true, `network=false`, and version
`1.1.3`.

Clean artifact SHA-256 values:

```text
wheel 0a049409907a47a89be038f9894e922b9cc0bd79350ddfb7f25c8d731150868c
sdist 81d3ee7e6278e0c731991880033f032a34561d0d5fc3bcbe0d878ab1a6e2ff9c
```

## Decision

**PASS for the Slice 187 bounded claim-next boundary and exact clean archive
package gate.** Overall release status remains conditional. No publication,
deployment, cloud action, registry write, or website update was performed.
