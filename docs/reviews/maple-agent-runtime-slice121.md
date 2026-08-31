# Code Review - MAPLE Agent Runtime Slice 121 @ 0ca0924

**Reviewer role:** Code Reviewer · **Date:** 2026-08-27  
**Reviewed against:** [project brief](../briefs/maple-agent-runtime-release.md),
[ADR-067](../adr/067-bounded-authenticated-event-ingestion.md), and the Slice
121 entry in the [implementation plan](../plans/maple-agent-runtime-release.md)

## Review evidence

```text
36 passed in 10.07s
345 passed in 11.94s
1307 passed, 1 skipped in 213.45s (0:03:33)
2 files would be left unchanged.
All checks passed!
Success: no issues found in 1 source file
doctor: ready=true, all eight checks true, network=false
git diff --check: no output (exit 0)
```

The reviewed runtime commits are `1b6e0fb`, `567fdfd`, and `0ca0924`:
authenticated event ingestion plus bounded early request-body draining.

## Findings

| # | Sev | Location | Finding | Suggested fix | Resolution |
|---|---|---|---|---|---|
| 1 | — | `maple/autonomy/server.py` event and early-response boundaries | No open correctness or security finding in the scoped diff. | Preserve receiver-owned event ordering/redaction and keep early-body draining bounded. | accepted by design |

## Scope check

The feature adds an optional authenticated `POST /v1/events` receiver,
`RunClient.publish_event(...)` coverage, exporter round-trip coverage, and the
small request-body drain needed to preserve typed early responses on Windows.
It updates the ADR, API reference, README, parity matrix, plan, and changelog;
it adds no dependency and does not publish or alter the website.

Review specifically covered:

- bearer authentication being mandatory when an event stream is exposed;
- receiver assignment of sequence and timestamp values instead of trusting
  remote envelope metadata;
- reuse of `EventStream` redaction, retention, payload limits, subscriber
  isolation, and local metrics;
- missing-stream, malformed-input, unauthorized, and oversized-body failures;
- bounded draining for early POST responses without weakening request limits;
  and
- preservation of existing workflow, agent, handoff, human-input, and event
  exporter routes.

The bearer token authenticates transport access but does not establish
per-principal authorization or tenancy. The ADR documents that limitation.
Remote batching, durable replay, aggregation, search, and exactly-once effects
remain separate reviewed boundaries.

## Verdict

- [x] Pass (0 open BLOCKERs or MAJORs)
- [ ] Return to build - findings above

Final publication remains vetoed by the separate environment-wide
dependency-governance finding recorded in the QA report.
