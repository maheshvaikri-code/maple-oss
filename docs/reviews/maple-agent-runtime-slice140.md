# MAPLE Agent Runtime Slice 140 Review

Date: 2026-08-27

Scope reviewed: `GuardrailEvent`, `GuardrailObserver`, `run_guardrails(...)`
observer behavior, sync/async agent event publication, exports, focused
regressions, ADR-085, API/README/parity documentation, changelog, and release
plan updates.

## Findings

- Guardrails retain ordered synchronous execution and fail-closed behavior;
  the new observer is additive and cannot weaken a policy decision.
- Lifecycle states distinguish started, passed, rejected, and failed outcomes,
  including malformed callbacks and callback exceptions.
- Event records validate bounded stage/index/status/correlation metadata and do
  not retain guarded values, prompts, raw error messages, or rejection payloads.
- Agent event publication links input transitions to the local run/goal and
  output transitions to the local run plus active model span where available;
  dropped event publication does not change the run result.
- The feature adds no dependency, network call, retry, bypass, remote policy
  engine, principal scope, hosted audit guarantee, or exactly-once effect claim.

## Disposition

Author-side review: no blocking finding for this slice. A fresh independent
verifier session was not available in this environment, so this record is not
represented as independent verifier approval. Async guardrail callback
execution, remote policy evaluation, durable policy decisions, and mandatory
hosted audit remain separate boundaries.
