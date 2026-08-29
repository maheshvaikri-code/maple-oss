# Slice 191 QA - owner-safe authenticated remote task start

**Date:** 2026-08-29
**QA role:** QA Engineer local pass
**Implementation commit:** `08f71e1`

## Behavior matrix

| Area | Result | Evidence |
|---|---|---|
| Authentication and scope | PASS | `POST /v1/tasks/{task_id}/start` requires `task:start`; a principal without that scope is rejected |
| Owner enforcement | PASS | Only the recorded assigned agent can start the task; mismatched owners fail with `TASK_CONFLICT` |
| State transition | PASS | Only `ASSIGNED` tasks transition to `RUNNING`; queued, repeated, and terminal starts fail without mutation |
| Timestamp and statistics | PASS | Accepted starts record `started_at` and preserve the queue's existing `running_tasks` accounting |
| Input validation | PASS | Invalid task IDs, actor IDs, and request fields are rejected before queue mutation |
| Durable queue parity | PASS | `FileTaskQueue` persists the running state and applies existing restart recovery to interrupted work |
| Existing lifecycle compatibility | PASS | Autonomy/task-management and full workspace suites remain green |
| Package/install/doctor | PASS | Exact clean archive builds, passes Twine, imports in an isolated venv, and doctor is network-free and ready |

## Executed evidence

```text
focused server + durable queue: 80 passed in 29.76s
autonomy + task-management: 800 passed in 74.75s
full dirty workspace: 1756 passed, 1 skipped in 316.99s
clean archive: 1639 passed, 1 skipped in 259.10s
clean package: build 0, Twine PASSED, install 0, import 0, doctor 0
```

The exact `08f71e1` archive contained `894` entries, the wheel contained `108`
members, and the sdist contained `808` members. The isolated doctor reported
all eight checks true, `network=false`, `ready=true`, and package version
`1.1.3`.

## Release disposition

Slice191 is QA-complete for its bounded local worker lifecycle contract. It is
not a release approval for v1.1.4: version promotion, a clean final release
commit on `main`, independent verifier/security availability, dependency
governance, and human publication authorization remain open. No external
publication, cloud, or website action was performed.
