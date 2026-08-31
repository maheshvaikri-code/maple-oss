# Slice 186 QA — authenticated remote task-queue control plane

**Date:** 2026-08-28
**QA role:** QA Engineer local pass
**Implementation commit:** `f4d518f`

## Behavior matrix

| Area | Result | Evidence |
|---|---|---|
| Authenticated submit/list/inspect/claim/complete round trip | PASS | `tests/autonomy/test_server.py`, task control round-trip regression |
| Queue ownership conflict | PASS | Wrong worker completion returns `TASK_CONFLICT` and does not mutate the task |
| Principal scope/agent/capability policy | PASS | Scope denial occurs before body use; exact worker and capability allowlists are enforced |
| Input and query bounds | PASS | Unknown fields, duplicate query parameters, invalid JSON result values, and bounded values fail closed |
| Queue configuration | PASS | Configuring a queue without authentication raises `ValueError`; missing queue returns typed `503` |
| Existing runtime compatibility | PASS | Autonomy/task-management suite and full workspace suite remain green |
| Package/install/doctor | PASS | Exact clean archive builds and imports task-management exports; doctor is network-free and ready |

## Executed evidence

```text
focused server: 59 passed in 33.19s
autonomy + task-management: 790 passed in 70.73s
full workspace: 1746 passed, 1 skipped in 309.92s (0:05:09)
clean archive: 1629 passed, 1 skipped in 253.53s
clean package: build 0, Twine PASSED, install 0, import 0, doctor 0
```

The clean archive contained `869` source entries, a `108`-entry wheel, and a
`783`-entry sdist. The isolated doctor reported all eight checks true,
`network=false`, `ready=true`, and package version `1.1.3`.

## Release disposition

Slice 186 is QA-complete for its stated local/process-boundary contract. It is
not a release approval for v1.1.4: version promotion, a clean final release
commit on `main`, independent verifier/security availability, dependency
governance, and human publication authorization remain open. No external
publication, cloud, or website action was performed.
