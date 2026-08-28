# Code Review - durable receiver-side event deduplication

**Review basis:** `f5abe63` plus verification corrections through `81e8dcf`
**Brief:** `docs/briefs/maple-agent-runtime-slice166.md`
**ADR:** `docs/adr/111-durable-event-deduplication.md`
**Date:** 2026-08-28
**Role:** Code Reviewer

## Decision

Pass.

## Review coverage

- Reviewed the new `FileEventDeduplicationStore` against the existing
  `EventDeduplicationStore` protocol and the in-memory state machine.
- Verified that persisted records contain only source identity, fingerprint,
  expiry, and the already-redacted destination event; source event payloads
  are not copied into the state file.
- Verified versioned full-document validation, bounded entry/byte/TTL limits,
  path ownership, atomic temporary-file replacement, durable local lease
  fencing, and typed load/save/lease failures.
- Verified matching completed claims replay a copied destination event,
  pending claims fail closed, conflicting fingerprints fail closed, and
  capacity eviction selects completed records rather than in-flight claims.
- Reviewed package exports, API documentation, README example, changelog, and
  parity wording for the local-only and at-least-once boundaries.
- The HTTP restart regression constructs a fresh file-backed store instance
  for each receiver instance and confirms the destination stream retains one
  event.

## Findings

No correctness, compatibility, or security blocker was found.

The implementation deliberately does not provide a distributed coordinator,
automatic retry loop, broker delivery, or exactly-once external side effects.
Expiry, capacity, and use of separate receiver directories can reopen the
duplicate window and are documented as such.

## Verification

```text
python -m pytest tests/autonomy/test_events.py -q --no-cov
45 passed in 4.30s

python -m pytest tests/autonomy/test_events.py tests/autonomy/test_server.py -q --no-cov
85 passed in 22.45s
```

The staged implementation diff passed `git diff --cached --check` before
commit. Review findings are closed; G4 passes. No publication, deployment,
cloud action, or website update was performed.
