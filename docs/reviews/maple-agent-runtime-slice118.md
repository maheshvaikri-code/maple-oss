# Code Review - MAPLE Agent Runtime Slice 118 @ a6e3575

**Reviewer role:** Code Reviewer · **Date:** 2026-08-27  
**Reviewed against:** [project brief](../briefs/maple-agent-runtime-release.md),
[ADR-064](../adr/064-bounded-authenticated-agent-run-transport.md), and the
Slice 118 entry in the [implementation plan](../plans/maple-agent-runtime-release.md)

## Review evidence

```text
14 passed in 5.68s
338 passed in 7.52s
1300 passed, 1 skipped in 212.14s (0:03:32)
97 files would be left unchanged.
All checks passed!
Success: no issues found in 3 source files
doctor: ready=true, all eight checks true, network=false
git diff --check: no output (exit 0)
```

The reviewed commit is `a6e3575`, `feat(transport): add bounded agent run
endpoint`.

## Findings

| # | Sev | Location | Finding | Suggested fix | Resolution |
|---|---|---|---|---|---|
| 1 | — | `maple/autonomy/server.py` agent transport boundary | No open correctness or security finding in the scoped diff. | Keep the one-way, authenticated, bounded contract and reopen ADR-064 before adding retries or remote state. | accepted by design |

## Scope check

The feature diff adds `AgentRegistry`, `AgentRun`, and `AgentRunHandler`,
optional authenticated `RunServer` agent routing, `RunClient.run_agent(...)`,
bounded JSON/task/identifier validation, typed result identity checks,
exception redaction, public exports, server regressions, ADR/API/README/
parity/changelog/plan documentation, and no new dependency.

Review specifically covered:

- authentication being mandatory when agent handlers are exposed;
- loopback-only server binding and existing bearer-token comparison;
- request, path, response, task, context, and result bounds;
- handler exception redaction and malformed-result rejection;
- request/response agent and run identity binding;
- no automatic retries, duplicate suppression, or exactly-once implication;
- backward compatibility for existing workflow and human-input routes; and
- preservation of untracked user-owned Doctrine files.

The implementation does not claim hosted scheduling, remote durable handoff
ownership, cancellation, resume, streaming, TLS termination, tenancy, or
exactly-once external effects.

## Verdict

- [x] Pass (0 open BLOCKERs or MAJORs)
- [ ] Return to build - findings above

The feature review passes. Final publication remains vetoed by the separate
environment-wide dependency-governance finding recorded in the QA report.
