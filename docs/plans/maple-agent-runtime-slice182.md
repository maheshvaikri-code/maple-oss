# Implementation Plan - Bounded agent route-policy validation

**Brief:** maple-agent-runtime-slice182 (docs/briefs/maple-agent-runtime-slice182.md) - **Design/ADR:** ADR-127 (docs/adr/127-bounded-agent-route-policy-validation.md) - **Class:** M

## Slices

| # | Slice | Role | Files touched | Proven by (tests) | Status |
|---|-------|------|---------------|-------------------|--------|
| 1 | Normalize route allowlist inputs | Backend / Security | maple/autonomy/server.py | Typed invalid-policy errors; valid/None compatibility | complete: implementation checkpoint |
| 2 | Add malformed-policy and no-handler regressions | QA / Security | tests/autonomy/test_server.py | Strings, duplicates, overflow, unhashable values, empty allowlist | complete: 55 focused; 1725 full passed, 1 skipped |
| 3 | Review, public records, and package evidence | Tech Writer / Release | QA/review/release artifacts | Full/static/clean archive/package checks | in progress: implementation review and public docs |

## Threat sketch

Assets touched: agent routing policy and handler side effects. Entry points:
arbitrary iterable policy values, malformed identifiers, duplicate entries,
oversized lists, and unhashable values. Worst plausible abuse: an invalid
allowlist crashes the request path or bypasses the intended policy boundary.

Mitigations: bounded exact normalization before registry lookup, typed errors,
no handler invocation on normalization failure, and compatibility tests for
None, valid tuples, and empty tuples.

## Status snapshot

Done (with evidence): design brief and ADR, route-policy normalization, and
malformed-input regressions. Next: public records and clean package evidence.
Blocked on: none.
