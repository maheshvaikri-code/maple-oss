# Slice 194 plan - owner-safe task heartbeat signal

**Brief:** [maple-agent-runtime-slice194.md](../briefs/maple-agent-runtime-slice194.md)
**Design/ADR:** [ADR-138](../adr/138-owner-safe-task-heartbeat.md)
**Class:** L

## Slices

| # | Slice | Role | Files touched | Proven by (tests) | Status |
|---|---|---|---|---|---|
| 1 | Queue model and durable record compatibility | Backend / Database | task queue, durable queue, queue tests | Owner/state checks, monotonic timestamp, legacy record load, restart persistence | complete |
| 2 | Authenticated transport | Backend / Interop / Security | server, client, server tests, API docs | Scope, principal policy, route/body bounds, stable errors, detached envelope | complete |
| 3 | Release evidence | QA / Code Reviewer / Release | README, parity, changelog, review/QA/release docs | Focused/full regression, static checks, clean/current package smoke | complete |

## Threat sketch

Assets touched: task ownership, durable task records, activity telemetry, and
authenticated queue transport. Entry points / untrusted inputs: task IDs,
worker IDs, bearer principals, HTTP method/path/body, and legacy JSON records.
Worst plausible abuse: an unauthorized worker overwrites activity telemetry or
uses malformed input to corrupt a durable queue; owner/state checks, bounded
parsing, monotonic updates, atomic persistence, and fail-closed route errors
contain the boundary.

## Risks and rollback points

- Risk: adding a durable field rejects old state â†’ accept both legacy and new
  record shapes and test restart compatibility â†’ rollback the additive field
  and route while preserving existing records.
- Risk: callers infer liveness from a timestamp â†’ document telemetry-only
  semantics in README/API/parity/ADR â†’ remove the route if a future contract
  cannot define its authority.
- Risk: duplicate delivery moves time backward â†’ store the maximum observed
  timestamp and test out-of-order calls â†’ revert only the monotonic update,
  not ownership checks.

## Deviation log

- None.

## Status snapshot

Implementation and release evidence are complete for this local
telemetry-only slice. Focused, full dirty-worktree, exact clean-archive,
static, package, install, and doctor gates passed. Distributed liveness remains
outside scope.
