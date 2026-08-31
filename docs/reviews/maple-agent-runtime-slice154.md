# MAPLE Agent Runtime Slice 154 Review Record

Date: 2026-08-28

## Review scope

Reviewed `maple/task_management/scheduler.py`, scheduler lifecycle regressions,
ADR-099, API reference, README, parity ledger, changelog, release plan, and
the QA record.

## Findings

No blocking defect found in the reviewed boundary.

`TaskScheduler` now reserves capacity while holding its own lock before
calling the queue. A queue rejection removes that reservation; a successful
claim retains it as the active assignment. This closes the race between a
capacity read and the later load increment while leaving queue ownership and
task state authoritative.

The queue call remains outside the scheduler lock, so user task callbacks are
not run while scheduler bookkeeping is locked. The reservation is local and
does not add distributed quotas, worker heartbeats, durable recovery, or
exactly-once effects.

## Release risks retained

- Environment-wide dependency governance remains a release veto:
  `pip-audit` reports `384 known vulnerabilities in 77 packages`, with local
  non-PyPI packages skipped.
- Bandit is unavailable in this environment, so no Bandit pass is claimed.
- A process crash during a claim can still require host-level reconciliation;
  this slice does not add durable reservations or worker liveness.
- A fresh independent verifier session was unavailable in this tool context;
  this record is not a substitute for that required independent review.

## Decision

Approve the atomic capacity-admission implementation for preview release
readiness. Exact-suite, static, and clean-archive package evidence are
recorded in the QA record. No publication, deployment, cloud action, or
website update was performed.
