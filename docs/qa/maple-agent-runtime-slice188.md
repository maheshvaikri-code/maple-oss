# Slice 188 QA - owner-safe remote task cancellation

**Date:** 2026-08-29
**QA role:** QA Engineer local pass
**Implementation commit:** `10d37fe`

## Behavior matrix

| Area | Result | Evidence |
|---|---|---|
| Authenticated route and scope | PASS | `task:cancel` is required for `POST /v1/tasks/{task_id}/cancel`; a principal without the scope is rejected |
| Queued cancellation | PASS | An authorized assigned-agent request transitions an unassigned queued task to `cancelled` |
| Assigned/running ownership | PASS | A mismatched owner receives `TASK_CONFLICT`; the recorded owner can cancel through the same atomic queue path |
| Terminal-state protection | PASS | Completed work cannot be cancelled through the owner-aware remote path |
| Malformed input | PASS | Unknown request fields return `TASK_INPUT_INVALID` without mutation |
| Durable queue parity | PASS | `FileTaskQueue` persists owner-safe cancellation and preserves terminal state after restart |
| Local compatibility | PASS | Existing no-owner local cancellation tests remain green |
| Existing runtime compatibility | PASS | Autonomy/task-management and full workspace suites remain green |
| Package/install/doctor | PASS | Exact clean archive builds, passes Twine, imports in an isolated venv, and doctor is network-free and ready |

## Executed evidence

```text
focused server/task-management: 95 passed in 27.36s
autonomy + task-management: 240 passed in 48.73s
full dirty workspace: 1749 passed, 1 skipped in 305.28s
clean archive: 1632 passed, 1 skipped in 257.84s
clean package: build 0, Twine PASSED, install 0, import 0, doctor 0
```

The exact `10d37fe` archive contained `879` entries, the wheel contained
`108` members, and the sdist contained `793` members. The isolated doctor
reported all eight checks true, `network=false`, `ready=true`, and package
version `1.1.3`.

## Release disposition

Slice 188 is QA-complete for its bounded process-boundary contract. It is not
a release approval for v1.1.4: version promotion, a clean final release
commit on `main`, independent verifier/security availability, dependency
governance, and human publication authorization remain open. No external
publication, cloud, or website action was performed.
