# Slice 77 QA - Bounded Agent Handoff Tools

**Role:** Chief Architect / Backend / Security / QA / Release  
**Commit:** `62ebad8`  
**Date:** 2026-08-25

## Scope

Expose one specialist agent's synchronous `pursue_goal` boundary as a normal
MAPLE tool, with approval-by-default, bounded task input, structured results,
and fail-closed target errors.

## Evidence

- Tool regression: `18 passed in 0.25s`.
- Autonomy regression: `234 passed in 3.49s`.
- Public root import of `create_handoff_tool` passed.
- Ruff reports all checks passed.
- Black reports all changed files unchanged after formatting.
- Mypy reports `Success: no issues found in 93 source files`.
- `python -m compileall -q maple` passed.
- Exact-current wheel and sdist built as `maple_oss-1.1.3`; Twine reports
  `PASSED` for both artifacts.
- Network-free doctor reports all eight checks true with `ready: true`,
  `network: false`, version `1.1.3`.

## Boundary review

- The task input is a required string capped at 8,192 characters and rejects
  additional properties before the target is called.
- Handoffs require approval by default; trusted hosts can explicitly opt out.
- Target failures expose only a stable error type and target error type, not
  raw target payloads. Exceptions and invalid target results fail closed.
- The returned success shape includes `agent_id`, `goal_id`, `status`, and
  `result`.
- Async MAPLE turns use the existing executor-backed synchronous tool path;
  this slice does not claim durable routing, conversation transfer, distributed
  execution, or hard target cancellation.
- No dependency, provider, cloud, publication, or website change was made.
- The exact-current repository attempt on `2b7ea84` collected `1300` items,
  reached `90%`, entered the slow Doctrine-gold phase, and was interrupted
  without failure output or a pytest summary; the full-suite gate remains open.

## Decision

PASS for the slice. ADR-029 records the local handoff boundary and its limits.
Exact full-suite completion and fresh independent verification remain open.
