# Implementation Plan - Bounded Remote Agent Invocation Idempotency

**Brief:** [Slice171 brief](../briefs/maple-agent-runtime-slice171.md)
**Design/ADR:** [ADR-116](../adr/116-bounded-agent-invocation-idempotency.md)
**Class:** L

## Slices

| # | Slice | Role | Files touched | Proven by (tests) | Status |
|---|---|---|---|---|---|
| 1 | Add bounded claim/complete/abort contracts and memory/file stores | Backend / Security | `maple/autonomy/invocations.py`, autonomy exports, store tests | Key/digest validation, detached replay, conflict/in-progress behavior, expiry/capacity, file restart/corruption/fencing | done: `d824940`; store suite `12 passed` |
| 2 | Integrate keyed named and capability-routed invocations | Backend / Interop | `maple/autonomy/server.py`, client/server regressions | Claim before handler, complete after normalization, missing-store fail-closed, route identity, legacy wire compatibility | done: `1c19544`; transport suite `71 passed` |
| 3 | Close public contract and release gates | Tech Writer / Code Reviewer / QA / Release | README, API reference, parity ledger, changelog, `docs/reviews/`, `docs/qa/`, release plan | Focused/tracked tests, static/security checks, clean archive, install/import | done: `b6c4c0c`; focused `21 passed`; full `1670 passed, 1 skipped`; clean archive source `809`, wheel `106`, sdist `723`, build/Twine/install/import pass |

## Threat sketch

Assets touched: request keys and digests, bounded response envelopes, local
deduplication state, and agent handler side effects. Entry points are keyed
HTTP requests, direct store calls, concurrent callers, and persisted JSON.
Worst plausible abuse is resource exhaustion or replay/confusion across
different requests. Bounds, canonical digests, fencing, detached copies,
authentication, scope checks, and fail-closed conflicts limit the blast radius.

## Risks and rollback points

- Risk: a keyed request silently executes without a store -> mitigation: fail
  closed with `AGENT_INVOCATION_STORE_UNAVAILABLE` -> rollback: remove only
  the optional keyed field and store integration; unkeyed invocation remains.
- Risk: replayed response belongs to a different request -> mitigation: bind
  target and all normalized request fields into a canonical digest -> rollback:
  disable replay while retaining conflict records for diagnosis.
- Risk: storage completion fails after handler execution -> mitigation: surface
  the storage error and never invoke again automatically -> rollback: keep the
  claim pending for explicit operator expiry/cleanup.
- Risk: persisted state leaks raw prompts or context -> mitigation: retain only
  digest and normalized response envelope; test serialized file contents ->
  rollback: disable file store while memory store remains available.

## Deviation log (append-only, as they happen)

- None.

## Status snapshot

G0 through G3 are recorded. Store, transport, public-contract, review, QA, and
clean-archive package gates are complete for this slice. Publication
authorization, cloud actions, and website changes remain outside this plan.
