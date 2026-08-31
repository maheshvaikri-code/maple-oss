# MAPLE Agent Runtime Slice 157 Review Record

Date: 2026-08-28

## Review scope

Reviewed `maple/autonomy/agent.py`, durable run regressions, ADR-102, API
reference, parity ledger, changelog, release plan, and the Slice 157 QA
record.

## Findings

No blocking defect found in the reviewed boundary.

Both sync and async resume paths now confirm that the authoritative pending
request's `tool_call_id` is present in the persisted tool-result messages
before any approval execution, approval replay, human-input consumption, or
checkpoint clearing. A mismatch returns `RUN_PENDING_TOOL_MISSING`; the
regressions prove handler calls, input consumption, and pending-state removal
do not occur.

## Release risks retained

- Environment-wide dependency governance remains a release veto:
  `pip-audit` reports `384 known vulnerabilities in 77 packages`, with local
  non-PyPI packages skipped.
- Bandit is unavailable in this environment, so no Bandit pass is claimed.
- Correlation is local to the persisted checkpoint and request record; it does
  not provide globally unique IDs, remote repair, distributed delivery, or
  exactly-once external effects.
- A fresh independent verifier session was unavailable in this tool context;
  this record is not a substitute for that required independent review.

## Decision

Approve the pending-request correlation implementation for preview release
readiness. Exact-suite, static, and clean-archive package evidence are
recorded in the QA record. No publication, deployment, cloud action, or
website update was performed.
