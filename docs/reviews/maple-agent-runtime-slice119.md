# Code Review - MAPLE Agent Runtime Slice 119 @ cafff3c

**Reviewer role:** Code Reviewer · **Date:** 2026-08-27  
**Reviewed against:** [project brief](../briefs/maple-agent-runtime-release.md),
[ADR-065](../adr/065-bounded-authenticated-handoff-transport.md), and the
Slice 119 entry in the [implementation plan](../plans/maple-agent-runtime-release.md)

## Review evidence

```text
16 passed in 6.24s
340 passed in 9.27s
1302 passed, 1 skipped in 214.52s (0:03:34)
97 files would be left unchanged.
All checks passed!
Success: no issues found in 3 source files
doctor: ready=true, all eight checks true, network=false
git diff --check: no output (exit 0)
```

The reviewed commit is `cafff3c`, `feat(transport): add bounded handoff
routes`.

## Findings

| # | Sev | Location | Finding | Suggested fix | Resolution |
|---|---|---|---|---|---|
| 1 | — | `maple/autonomy/server.py` handoff transport boundary | No open correctness or security finding in the scoped diff. | Keep digest-only payloads and store-owned state transitions; reopen ADR-065 before adding principal scopes or delivery semantics. | accepted by design |

## Scope check

The feature diff adds optional authenticated handoff routing to the existing
dependency-free server, client helpers for create/inspect/list/accept/
complete/fail, typed status mapping, server regressions, ADR/API/README/
parity/changelog/plan documentation, and no new dependency.

Review specifically covered:

- bearer authentication being mandatory when a handoff store is exposed;
- digest-only record serialization with no raw task/context transfer;
- existing store validation, ownership checks, terminal transitions, and
  file-fencing semantics remaining in control;
- malformed record and bounded-list failure paths;
- unauthorized, missing-store, not-found, owner-conflict, and state-conflict
  responses;
- absence of retries, queueing, notifications, scheduling, and exactly-once
  implications; and
- preservation of existing workflow, agent-run, and human-input routes.

The bearer token authenticates transport access but does not establish a
per-agent principal or authorization scope; the ADR documents that host-owned
limitation and the need for a reviewed proxy/identity layer for non-loopback
deployment.

## Verdict

- [x] Pass (0 open BLOCKERs or MAJORs)
- [ ] Return to build - findings above

The feature review passes. Final publication remains vetoed by the separate
environment-wide dependency-governance finding recorded in the QA report.
