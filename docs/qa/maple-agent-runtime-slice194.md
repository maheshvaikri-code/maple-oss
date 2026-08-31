# Slice 194 QA - owner-safe task heartbeat signal

**Date:** 2026-08-29
**QA role:** QA Engineer local pass
**Implementation commit:** `bb7690c`

## Behavior matrix

| Area | Result | Evidence |
|---|---|---|
| Owner and active-state enforcement | PASS | Only the recorded owner can heartbeat `ASSIGNED` or `RUNNING` tasks; queued, terminal, missing, and wrong-owner requests are rejected |
| Monotonic telemetry | PASS | Older observations do not replace a newer `heartbeat_at` value |
| Durable compatibility | PASS | New heartbeats persist; legacy records without `heartbeat_at` load with `None`; restart recovery remains safe |
| Transport authorization | PASS | `task:heartbeat`, exact body, principal-agent policy, malformed input, and bounded task envelope are covered |
| Side-effect boundary | PASS | Heartbeat does not notify status callbacks, execute handlers, renew leases, expire work, reassign tasks, or schedule work |
| Focused regressions | PASS | Queue/server suites: `105 passed in 30.91s` |
| Full workspace regression | PASS | `1759 passed, 1 skipped in 324.36s` |
| Clean archive regression | PASS | `1642 passed, 1 skipped in 255.17s` at `bb7690c` |
| Whole-package typing | PASS | `mypy maple/ --ignore-missing-imports`: no issues in 101 source files |
| Package/install/doctor | PASS | Clean wheel/sdist build, Twine, isolated install/import, and network-free doctor pass |

## Executed evidence

```text
clean archive entries: 906 tar-listed entries
wheel members: 108
sdist members: 820
wheel sha256: c2cbb87d01336d170c19d0f17ccf353b79588dc30804de6f3cad3bbb89738f23
sdist sha256: e7bec4554d1c1c5e6f23541c09007edd702b6dfb7de33fea45b8108a45f1e5e5
doctor: status=SUCCESS, ready=true, network=false, version=1.1.3
```

The declared-project dependency audit exited `0` with `No known
vulnerabilities found`. The shared environment audit remains a governance
veto at `385` findings across `78` packages. Bandit, Gitleaks, and a fresh
independent verifier session were unavailable in this tool context; none is
claimed as passed.

## Release disposition

Slice194 is QA-complete for its bounded owner-safe telemetry contract and
exact clean archive package gate. It is not a release approval for v1.1.4:
version promotion, a clean final release commit on `main`, dependency
governance, unavailable security/verifier tools, and human publication
authorization remain open. No external publication, cloud, or website action
was performed.
