# Code Review - MAPLE Agent Runtime Slice 164

**Date:** 2026-08-28  
**Reviewer role:** Code Reviewer  
**Review basis:** Slice164 brief and ADR-109, plus implementation candidate
`21fc4bc`  
**Decision:** Pass with no blocking findings

## Reviewed surface

- `create_agent_tool` persistent-child option and sync/async dispatch.
- Signature validation for child start and resume methods.
- Bounded child-run ID validation and schema exposure.
- Existing cancellation propagation, context allowlisting, result
  normalization, and error redaction.
- Public API, README, parity ledger, changelog, and release-plan updates.

## Findings

No blocking findings.

The implementation keeps `persist_child_run=False` as the default, requires a
caller-owned ID only in the opt-in mode, and validates the native run/resume
contract before constructing the persistent tool. A retry only switches to
resume for the exact `RUN_EXISTS` error; arbitrary target failures are not
retried. Sync and async paths use the corresponding native resume method, and
the cancellation token remains signature-gated. Result formatting continues
to omit raw child errors and exceptions.

The existence probe necessarily calls the child's start method once more on a
retry. Native `AutonomousAgent.pursue_goal` checks its run store before model
side effects, and the following resume call owns checkpoint continuation. The
ADR now states this distinction explicitly.

## Explicit boundaries retained

- No second child persistence store or cross-store transaction was added.
- Completed terminal child results are not independently replayed by this
  option; the existing parent execution journal remains the replay contract.
- Remote routing, distributed scheduling, hard cancellation, rollback, and
  exactly-once external effects remain unclaimed.

## Verification status

Behavioral and static gate results are recorded in the Slice164 QA artifact
after the full suite and package checks complete.
