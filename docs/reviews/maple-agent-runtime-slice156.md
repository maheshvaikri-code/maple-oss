# MAPLE Agent Runtime Slice 156 Review Record

Date: 2026-08-28

## Review scope

Reviewed `maple/autonomy/runs.py`, durable run regressions, run lease
regressions, ADR-101, API reference, parity ledger, changelog, release plan,
and the Slice 156 QA record.

## Findings

No blocking defect found in the reviewed boundary.

Checkpoint normalization rejects both pending request IDs, requires exactly
one request ID for a paused checkpoint, and rejects pending IDs on running or
terminal checkpoints. The existing memory and file stores invoke this parser
before mutation, while valid sync/async resume paths retain their existing
behavior. The regression suite proves rejected saves do not replace an
existing record.

## Release risks retained

- Environment-wide dependency governance remains a release veto:
  `pip-audit` reports `384 known vulnerabilities in 77 packages`, with local
  non-PyPI packages skipped.
- Bandit is unavailable in this environment, so no Bandit pass is claimed.
- The invariant does not bind request IDs to globally unique tool calls,
  deliver notifications, coordinate distributed recovery, or establish
  exactly-once external effects.
- A fresh independent verifier session was unavailable in this tool context;
  this record is not a substitute for that required independent review.

## Decision

Approve the checkpoint-integrity implementation for preview release
readiness. Exact-suite, static, and clean-archive package evidence are
recorded in the QA record. No publication, deployment, cloud action, or
website update was performed.
