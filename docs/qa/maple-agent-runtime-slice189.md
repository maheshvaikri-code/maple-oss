# Slice 189 QA - owner-safe remote task retry

**Date:** 2026-08-29
**QA role:** QA Engineer local pass
**Implementation commit:** `13c5956`

## Behavior matrix

| Area | Result | Evidence |
|---|---|---|
| Authenticated route and scope | PASS | `task:retry` is required for `POST /v1/tasks/{task_id}/retry`; a principal without the scope is rejected |
| Failed-state requirement | PASS | Queued, completed, cancelled, running, and other non-failed states cannot use the owner-aware retry path |
| Owner matching | PASS | A mismatched owner receives `TASK_CONFLICT`; the recorded owner can explicitly requeue failed work |
| Retry and capacity bounds | PASS | Retry count and queue capacity remain authoritative; exhausted retry is normalized as `TASK_CONFLICT` |
| Requeue response | PASS | Successful retry returns queued status, clears the owner, and increments `retry_count` |
| Malformed input | PASS | Unknown request fields return `TASK_INPUT_INVALID` without mutation |
| Durable queue parity | PASS | `FileTaskQueue` persists owner-safe retry and preserves the final state after restart |
| Local compatibility | PASS | Existing no-owner local requeue tests remain green |
| Existing runtime compatibility | PASS | Autonomy/task-management and full workspace suites remain green |
| Package/install/doctor | PASS | Exact clean archive builds, passes Twine, imports in an isolated venv, and doctor is network-free and ready |

## Executed evidence

```text
focused server/task-management: 97 passed in 27.88s
autonomy + task-management: 795 passed in 72.22s
full dirty workspace: 1751 passed, 1 skipped in 312.60s
clean archive: 1634 passed, 1 skipped in 260.53s
clean package: build 0, Twine PASSED, install 0, import 0, doctor 0
```

The exact `13c5956` archive contained `884` entries, the wheel contained
`108` members, and the sdist contained `798` members. The isolated doctor
reported all eight checks true, `network=false`, `ready=true`, and package
version `1.1.3`.

## Release disposition

Slice 189 is QA-complete for its bounded process-boundary contract. It is not
a release approval for v1.1.4: version promotion, a clean final release
commit on `main`, independent verifier/security availability, dependency
governance, and human publication authorization remain open. No external
publication, cloud, or website action was performed.
