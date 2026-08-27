# Code Review - MAPLE Agent Runtime Slice 120 @ 9d1d7aa

**Reviewer role:** Code Reviewer · **Date:** 2026-08-27  
**Reviewed against:** [project brief](../briefs/maple-agent-runtime-release.md),
[ADR-066](../adr/066-bounded-authenticated-durable-agent-run-transport.md), and
the Slice 120 entry in the [implementation plan](../plans/maple-agent-runtime-release.md)

## Review evidence

```text
18 passed in 10.19s
342 passed in 14.06s
1304 passed, 1 skipped in 224.03s (0:03:44)
4 files would be left unchanged.
All checks passed!
Success: no issues found in 3 source files
doctor: ready=true, all eight checks true, network=false
git diff --check: no output (exit 0)
```

The reviewed commit is `9d1d7aa`, `feat(transport): add durable agent run
control`.

## Findings

| # | Sev | Location | Finding | Suggested fix | Resolution |
|---|---|---|---|---|---|
| 1 | — | `maple/autonomy/server.py` durable agent transport boundary | No open correctness or security finding in the scoped diff. | Keep resume explicit and keep transcript fields off-wire; reopen ADR-066 before adding scheduler, principal scopes, or delivery semantics. | accepted by design |

## Scope check

The feature diff adds an optional durable checkpoint inspection route, an
explicit resume callback registry seam, client helpers, typed status mapping,
regressions, ADR/API/README/parity/changelog/plan documentation, and no new
dependency.

Review specifically covered:

- bearer authentication being mandatory when an agent registry or run store is
  exposed;
- checkpoint identity matching the URL agent and cross-agent records returning
  not found;
- transcript and reasoning-trace omission from the remote response;
- resume not being inferred from the original invocation handler;
- callback exceptions and malformed envelopes failing closed;
- reuse of existing store validation, durable leasing, and agent result
  normalization; and
- preservation of existing workflow, human-input, handoff, and one-way agent
  routes.

The bearer token authenticates transport access but does not establish a
per-agent principal or authorization scope. The ADR documents that limitation
and the need for a reviewed proxy/identity layer for non-loopback deployment.

## Verdict

- [x] Pass (0 open BLOCKERs or MAJORs)
- [ ] Return to build - findings above

Final publication remains vetoed by the separate environment-wide
dependency-governance finding recorded in the QA report.
