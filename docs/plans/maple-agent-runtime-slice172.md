# Implementation Plan - Opt-in Remote Handoff Invocation Idempotency

**Brief:** [Slice172 brief](../briefs/maple-agent-runtime-slice172.md)
**Design/ADR:** [ADR-117](../adr/117-remote-handoff-idempotency-binding.md)
**Class:** M

## Slices

| # | Slice | Role | Files touched | Proven by (tests) | Status |
|---|---|---|---|---|---|
| 1 | Add explicit adapter binding and input validation | Backend / Interop / Security | `maple/autonomy/server.py`, adapter regressions | Default wire compatibility, opt-in key/run binding, missing/invalid handoff ID, sync/async behavior | done: `21c4f2a`; focused `54 passed`; changed static/security gates pass |
| 2 | Close public contract and release gates | Tech Writer / Code Reviewer / QA / Release | README, API reference, parity ledger, changelog, `docs/reviews/`, `docs/qa/`, release plan | Focused/full tests, static/security checks, clean archive, install/import | done: `21c4f2a`; full `1674 passed, 1 skipped`; clean archive source `815`, wheel `106`, sdist `729`, build/Twine/install/import pass |

## Threat sketch

Assets are remote handler side effects, handoff identity, bearer-authenticated
request fields, and receiver deduplication state. Entry points are adapter
construction, sync/async handoff execution, missing IDs, and receiver replay or
conflict responses. The worst plausible abuse is false identity reuse or
repeated side effects. Explicit opt-in, bounded control-free IDs, receiver-side
canonical digests, existing authentication/scopes, and fail-closed store
requirements contain the blast radius.

## Rollback

Remove only the optional constructor flag and keyword forwarding. The default
adapter path and Slice 171 standalone client/store contract remain intact.

## Status snapshot

G0 and G1 are recorded. Implementation begins with the shared adapter path;
publication authorization, cloud actions, and website changes remain outside
this plan.
