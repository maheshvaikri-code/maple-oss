# Slice 187 QA - non-blocking remote claim-next

**Date:** 2026-08-28
**QA role:** QA Engineer local pass
**Implementation commit:** `2aabca9`

## Behavior matrix

| Area | Result | Evidence |
|---|---|---|
| Authenticated route and scope | PASS | `task:claim` authorization is required for `POST /v1/tasks/claim-next`; unauthorized callers are rejected |
| Capability matching | PASS | A worker claims only tasks whose exact requirements are in its declared capabilities |
| Priority and deterministic selection | PASS | Critical compatible work is selected before lower priority work; creation time and task ID provide tie-breakers |
| Incompatible task preservation | PASS | The incompatible `write` task remains queued after compatible `search` work is claimed |
| Explicit no-work result | PASS | A compatible poll with no remaining task returns `{"task": null}` without blocking |
| Principal policy | PASS | Allowed agent and capability policies are enforced before queue access/mutation |
| Queue ownership compatibility | PASS | Claims delegate to the existing atomic queue transition; Slice 186 ownership tests remain green |
| Existing runtime compatibility | PASS | Autonomy/task-management and full workspace suites remain green |
| Package/install/doctor | PASS | Exact clean archive builds, passes Twine, imports in an isolated venv, and doctor is network-free and ready |

## Executed evidence

```text
focused server: 60 passed in 25.97s
autonomy + task-management: 791 passed in 71.78s
full dirty workspace: 1747 passed, 1 skipped in 309.42s
clean archive: 1630 passed, 1 skipped in 254.93s
clean package: build 0, Twine PASSED, install 0, import 0, doctor 0
```

The exact `2aabca9` archive contained `874` entries, the wheel contained
`108` members, and the sdist contained `788` members. The isolated doctor
reported all eight checks true, `network=false`, `ready=true`, and package
version `1.1.3`.

## Release disposition

Slice 187 is QA-complete for its bounded process-boundary contract. It is not
a release approval for v1.1.4: version promotion, a clean final release
commit on `main`, independent verifier/security availability, dependency
governance, and human publication authorization remain open. No external
publication, cloud, or website action was performed.
