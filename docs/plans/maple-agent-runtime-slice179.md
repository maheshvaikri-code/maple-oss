# Implementation Plan - Optional cross-process notification drain fencing

**Brief:** [maple-agent-runtime-slice179](../briefs/maple-agent-runtime-slice179.md) · **Design/ADR:** [ADR-124](../adr/124-cross-process-notification-drain-fence.md) · **Class:** M

## Slices

| # | Slice | Role | Files touched | Proven by (tests) | Status |
|---|-------|------|---------------|-------------------|--------|
| 1 | Add optional durable outbox-wide lease ownership | Backend / Security | `maple/autonomy/notification_outbox.py`, exports | Acquisition fencing, no-target-on-denial, bounded TTL, release | todo |
| 2 | Prove compatibility and concurrent drain behavior | QA / Security | `tests/autonomy/test_notification_outbox.py` | Existing outbox suite plus competing worker and release/error cases | todo |
| 3 | Publish contract and package evidence | Tech Writer / Release | README, API/parity/changelog, QA/review/release artifacts | Static checks, full suite, clean archive, isolated package smoke | todo |

## Threat sketch

Assets touched: outbox ownership, notification payloads, lease state, and
downstream side effects. Entry points: lease-manager configuration, shared
lease state, TTL, competing drainers, target timing, and release results. Worst
plausible abuse: lease starvation, stale-owner delivery after expiry, or
duplicate downstream side effects.

Mitigations: caller-owned bounded `FileLeaseManager`, deterministic resource
identity, bounded TTL, typed acquire/release failures, target calls outside the
state lock, no automatic renewal, and explicit at-least-once documentation.

## Risks & rollback points

- Risk: a slow target exceeds the TTL → mitigation: bounded explicit TTL and
  truthful duplicate semantics → rollback: omit the lease option and retain
  in-process drain coordination.
- Risk: a stale or corrupt lease state blocks delivery → mitigation: existing
  file lease manager fails closed → rollback: remove lease-manager wiring.

## Deviation log

- None.

## Status snapshot

Done (with evidence): design brief and ADR. Next: implement optional lease
ownership. Blocked on: none.
