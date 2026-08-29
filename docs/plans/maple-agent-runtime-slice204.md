# Implementation Plan — trusted local task worker

**Brief:** [Slice 204 brief](../briefs/maple-agent-runtime-slice204.md)
**Design/ADR:** [ADR-148](../adr/148-trusted-local-task-worker.md)
**Class:** L

## Slices

| # | Slice | Role | Files touched | Proven by (tests) | Status |
|---|---|---|---|---|---|
| 1 | Queue filtering and trusted worker lifecycle | Backend / Security | `maple/task_management/task_queue.py`, `maple/task_management/durable_queue.py`, new `maple/task_management/worker.py`, worker tests | Configuration bounds, task-type filtering, ownership transitions, handler success/failure, cancellation, timeout and output limits, file restart | complete: focused worker/queue `56 passed`; full suite `1829 passed, 1 skipped` |
| 2 | Public documentation and package surface | Tech Writer / Interop | task-management exports, `README.md`, `docs/api-reference.md`, parity ledger, `CHANGELOG.md` | Import/export smoke, runnable API example, docs consistency checks | complete: import/export and runnable API example pass; docs and changelog updated |
| 3 | Independent review and verification evidence | Code Reviewer / QA / Security / Release | `docs/reviews/maple-agent-runtime-slice204.md`, `docs/qa/maple-agent-runtime-slice204.md`, release plan | Focused worker suite, task-management suite, full suite, format/lint/type/compile/package gates | complete locally: review/QA evidence filed; fresh independent verifier unavailable; package publication remains gated |

## Threat sketch

Assets touched: queued task payloads, task ownership, handler results, and
terminal error state. Entry points / untrusted inputs: task records, worker
configuration, task types, payloads, handler return values, and cancellation
timing. Worst plausible abuse: a host registers an unsafe handler or a task
payload causes excessive memory/output use; mitigation is explicit trusted-only
documentation, handler-type filtering, existing JSON/input/output bounds, and
owner-checked terminal transitions. This slice does not accept model code or
provide an isolation boundary.

## Risks and rollback points

- Risk: queue polling filters could starve work or alter existing callers →
  mitigation: optional filter preserves the current `None` path, and tests
  cover both filtered and legacy polling → rollback: revert the queue filter
  and worker module together.
- Risk: a timeout cannot forcibly stop Python code → mitigation: retain
  `TrustedLocalExecutor`'s explicit cooperative semantics and document the
  limitation → rollback: remove worker execution without touching queue state.
- Risk: a handler mutates a nested payload value → mitigation: detach the
  top-level mapping and keep the handler contract trusted-only → rollback:
  tighten the payload-copy contract in a follow-up ADR if hosts need deep
  immutable input.

## Deviation log

- None at plan creation.

## Status snapshot

Done: G0/G1/G2 brief, ADR, implementation, docs, tests, local review, and QA
evidence filed.
Next: package smoke and release-audit closure.
Blocked on: no blocker for this local trusted slice; Slice 199 isolation,
Slice 193 hosted coordination, Slice 200 CI policy, and publication remain
separate human-gated work.
