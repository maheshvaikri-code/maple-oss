# Implementation Plan - Bounded remote event and trace search

**Brief:** maple-agent-runtime-slice183 (docs/briefs/maple-agent-runtime-slice183.md) - **Design/ADR:** ADR-128 (docs/adr/128-bounded-remote-event-trace-search.md) - **Class:** M

## Slices

| # | Slice | Role | Files touched | Proven by (tests) | Status |
|---|-------|------|---------------|-------------------|--------|
| 1 | Add exact-filter retained-window search | Backend / Observability | maple/autonomy/events.py | Filter validation, order, bounds, cursor expiry, redacted trace matching | complete: implementation checkpoint |
| 2 | Add authenticated server/client transport | Backend / Interop / Security | maple/autonomy/server.py | `event:read`, typed query errors, remote response shape | complete: focused event/server tests |
| 3 | Review, public records, and package evidence | QA / Tech Writer / Release | API/parity/changelog/review/release artifacts | Full/static/clean archive/package checks | in progress |

## Threat sketch

Assets touched: retained redacted event metadata and remote diagnostic access.
Entry points: unsupported query keys, unbounded filters, cursor expiry, and
trace metadata. Worst plausible abuse: response amplification or accidental
exposure of unrelated/unredacted payload data.

Mitigations: exact bounded filter allowlist, required filter, existing stream
retention and response bounds, event redaction before retention/search, typed
cursor errors, and existing `event:read` authorization.

## Status snapshot

Done (with evidence): design brief and ADR, retained-window search, and
authenticated transport with focused regressions. Next: full/static review,
public records, and clean package evidence. Blocked on: none.
