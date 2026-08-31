# Code Review - MAPLE Agent Runtime Slice 122 @ 3642805

**Reviewer role:** Code Reviewer · **Date:** 2026-08-27  
**Reviewed against:** [project brief](../briefs/maple-agent-runtime-release.md),
[ADR-068](../adr/068-bounded-authenticated-event-inspection.md), and the Slice
122 entry in the [implementation plan](../plans/maple-agent-runtime-release.md)

## Review evidence

```text
37 passed in 10.68s
346 passed in 12.57s
1308 passed, 1 skipped in 226.26s (0:03:46)
2 files would be left unchanged.
All checks passed!
Success: no issues found in 1 source file
doctor: ready=true, all eight checks true, network=false
git diff --check: no output (exit 0)
```

The reviewed commit is `3642805`, adding authenticated bounded event inspection
by cursor on top of Slice 121's ingestion seam.

## Findings

| # | Sev | Location | Finding | Suggested fix | Resolution |
|---|---|---|---|---|---|
| 1 | — | `maple/autonomy/server.py` event inspection boundary | No open correctness or security finding in the scoped diff. | Keep query parsing strict and retain `EventStream` as the authority for cursor expiry, redaction, and retention. | accepted by design |

## Scope check

The feature adds an authenticated `GET /v1/events` cursor-read route,
`RunClient.read_events(...)`, strict query construction/parsing, explicit
retention-gap status mapping, tests, ADR/API/README/parity/plan/changelog
documentation, and no dependency.

Review specifically covered:

- bearer authentication before event inspection;
- one-value-only `after`/`limit` parsing and unknown-query rejection;
- the `1,000` remote batch cap and existing response bounds;
- receiver-owned redaction, sequence, timestamps, retention, and cursor expiry;
- typed `400`, `409`, and `503` failure behavior; and
- preservation of existing ingestion, exporter, workflow, agent, handoff, and
  human-input routes.

The route reads only the host-owned bounded ring. It does not establish
durable replay, batching, indexing, tenancy, principal authorization, fleet
aggregation, or exactly-once effects. Those remain separate reviewed
boundaries.

## Verdict

- [x] Pass (0 open BLOCKERs or MAJORs)
- [ ] Return to build - findings above

Final publication remains vetoed by the separate environment-wide
dependency-governance finding recorded in the QA report.
