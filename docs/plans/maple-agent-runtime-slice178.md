# Implementation Plan - Bounded durable notification outbox

**Brief:** [maple-agent-runtime-slice178](../briefs/maple-agent-runtime-slice178.md) · **Design/ADR:** [ADR-123](../adr/123-durable-notification-outbox.md) · **Class:** L

## Slices

| # | Slice | Role | Files touched | Proven by (tests) | Status |
|---|-------|------|---------------|-------------------|--------|
| 1 | Implement bounded generic file outbox and typed reports | Backend / Security | `maple/autonomy/notification_outbox.py`, exports | Atomic enqueue, canonical deduplication, restart load, malformed-state rejection, bounds | complete: implementation `995f659`; focused outbox suite `10 passed in 0.43s` |
| 2 | Add human-input and approval protocol adapters | Backend / Interop | `maple/autonomy/interactions.py`, `maple/autonomy/approval.py`, exports | Both built-in stores enqueue typed notifications; notifier compatibility remains green | complete: implementation `995f659`; focused compatibility set `34 passed in 4.64s` |
| 3 | Prove drain, failure, concurrency, and adversarial behavior | QA / Security | `tests/autonomy/test_notification_outbox.py` | Success mark, retained failure, explicit retry, sanitized state, no network under lock, no mutation on invalid state | complete: test additions `83336eb`; full workspace `1715 passed, 1 skipped in 280.37s`; Black/isort/Ruff/mypy changed-boundary/compile pass |
| 4 | Publish contract and package evidence | Tech Writer / Release | README, API/parity/changelog, QA/review/release artifacts | Static checks, full suite, clean archive, isolated import/package smoke | complete: public docs/review/QA `c064b80`; clean archive source `841`, clean suite `1598 passed, 1 skipped in 255.85s`, wheel `107`, sdist `755`, Twine/install/import/doctor pass |

## Threat sketch

Assets touched: notification payloads, tool arguments, approval metadata,
outbox state, downstream endpoint behavior, and filesystem paths. Entry points
and untrusted inputs: notification objects, JSON records, directory contents,
queue limits, notifier results/exceptions, and drain limits. Worst plausible
abuse: queue exhaustion, malformed-state execution, payload disclosure through
errors, or duplicate downstream side effects after an ambiguous success.

Mitigations: canonical bounded JSON, deterministic safe filenames, atomic
writes, strict schema/type/digest validation, finite record/queue/drain limits,
sanitized persisted errors, no payload logging, network calls outside the
state lock, explicit at-least-once documentation, and no automatic mutation
to free space.

## Risks & rollback points

- Risk: a process crash after downstream success can duplicate delivery →
  mitigation: retain deterministic identity and document at-least-once →
  rollback: stop using the adapters and retain existing one-shot notifiers.
- Risk: malformed disk state could block a drain → mitigation: fail closed and
  make no repair or deletion → rollback: remove the optional outbox wiring.
- Risk: queue limits reject a store notifier → mitigation: typed error and
  authoritative local store semantics remain visible → rollback: configure a
  direct notifier or increase bounded limits explicitly.

## Deviation log

- 2026-08-28: the first Windows archive pipeline used a PowerShell binary
  pipe and produced a damaged tar stream; the package gate was rerun with
  `git archive --output=...` in a fresh isolated temp directory, with no
  repository mutation.

## Status snapshot

Done (with evidence): design, implementation, focused regressions, full suite,
changed-boundary static gates, public docs, review/QA, and clean-archive
package evidence. Next: continue the remaining P0 parity gaps. Blocked on:
none.
