# Slice 201 plan — bounded session history and branching

**Brief:** [maple-agent-runtime-slice201.md](../briefs/maple-agent-runtime-slice201.md)  
**Design/ADR:** [ADR-145](../adr/145-bounded-session-history-and-forking.md)  
**Class:** L

## Slices

| # | Slice | Role | Files touched | Proven by (tests) | Status |
|---|---|---|---|---|---|
| 1 | Shared bounded history/fork contract and in-memory store | Backend / Interop | `maple/autonomy/sessions.py`, session tests, public exports | create/mutate history, newest-limit ordering, detached copies, fork/source immutability, conflicts and bounds | complete @ `b2f3809` |
| 2 | File envelope persistence and legacy compatibility | Backend / Security | `maple/autonomy/sessions.py`, session tests | restart history/fork, legacy direct snapshot load, atomic failure/no partial write, malformed history rejection | complete @ `b2f3809` |
| 3 | Public surface and release evidence | Tech Writer / Code Reviewer / QA / Security / Release | README, API reference, parity ledger, changelog, review/QA/release artifacts | runnable API examples, full regression, static checks, package smoke, scoped security review | complete for slice @ `b2f3809`; package smoke in G6 |

## Threat sketch

Assets touched: conversation messages, tool-call metadata, session metadata,
version history, and branch contents. Entry points / untrusted inputs:
session IDs, target IDs, history limits, version selectors, caller messages,
metadata, and persisted JSON files. Worst plausible abuse: an oversized or
malformed history consumes memory/disk, a stale branch overwrites a target, or
mutable nested data leaks between source and target; validation, hard bounds,
detached copies, optimistic checks, and atomic replacement address these local
risks.

## Risks & rollback points

- Risk: retaining snapshots exhausts the existing session byte budget →
  mitigation: count and byte bounds are checked before commit, with typed
  failure and no partial mutation → rollback: remove history retention while
  preserving the current snapshot format.
- Risk: current/history divergence after a file failure → mitigation: persist
  both in one atomic envelope and reject inconsistent records on load →
  rollback: keep legacy direct-snapshot reads and disable branching for invalid
  envelopes.
- Risk: callers mistake a fork for distributed lineage → mitigation: document
  independent version `0`, no implicit parent identity, and local-only scope →
  rollback: keep the API preview-only until lineage is specified.

## Deviation log (append-only, as they happen)

- None.

## Status snapshot

G0/G1/G2 design, implementation, review, and QA are complete for the local
contract. G6 package smoke remains for this slice. Hosted tenancy, distributed
coordination, encryption, and remote APIs remain separate human-gated scope.
