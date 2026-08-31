# Slice 201 brief — bounded session history and branching

**Date:** 2026-08-29  
**Class:** L (public session API and durable store schema)  
**Requested by:** human continuation request

## Problem

MAPLE session stores expose optimistic versions and compaction, but callers
cannot inspect retained prior states or explore a prior conversation without
mutating the current session. This limits local time-travel debugging,
branching workflows, and safe experimentation against the same conversation
context even though the stores already have bounded JSON snapshots.

## Scope

- In: bounded retained session snapshots for the built-in in-memory and file
  stores; chronological `history()` inspection; `fork()` from a retained
  version; optimistic version checks; legacy file-format compatibility; public
  exports and documentation.
- **Non-goals:** remote session APIs, distributed history coordination,
  encryption, automatic or token-aware summarization, history merging, model
  calls, handler execution, or replay of stored messages.
- Deferred (ideas parked during this task): hosted session storage, cross-host
  branch synchronization, retention policies based on age/cost, and visual
  session tooling.

## Acceptance criteria (numbered, testable)

1. Given a session and successful create/append/clear/compact mutations, when
   `history(session_id, limit=N)` is called, then it returns detached retained
   snapshots in ascending version order, limited to the newest `N` entries.
2. Given a retained source version, when `fork(source_id, target_id,
   at_version=V)` succeeds, then the target starts at version `0` with an
   exact detached copy of the source messages and metadata, while the source
   remains unchanged.
3. Given no `at_version`, when `fork()` succeeds, then it branches from the
   current tip; given a stale `expected_version`, an evicted version, a
   missing source, or an existing target, then it returns a typed error and
   creates no target or source mutation.
4. Given a file store restart, when history is loaded, then retained snapshots
   and their versions remain available; given a legacy single-snapshot file,
   then it loads as one retained version and is not rewritten merely by
   inspection.
5. Given invalid IDs, limits, malformed retained history, or a session record
   exceeding configured bytes, when history or fork is attempted, then the
   operation fails closed without partial mutation.
6. The public APIs are exported and documented, no dependency or network path
   is added, valid existing session behavior remains compatible, and focused
   plus full repository checks pass.

## Constraints

- Use the existing `SessionSnapshot`, `Result`, JSON validation, atomic file
  replacement, and session byte/message bounds.
- Retain at most `10,000` snapshots per session; default retention is `100`.
- The serialized current snapshot plus retained history must remain within the
  configured `max_session_bytes` limit.
- A branch has an independent version sequence starting at `0`; no source
  snapshot or message object may be shared mutably with the target.
- Preserve user-owned changes outside this slice.

## Assumptions (chosen defaults — correct me if wrong)

- History is chronological and returns the newest `limit` retained snapshots,
  so callers can inspect a bounded tail without an unbounded list.
- Retention is count-bounded and oldest snapshots are evicted after a newer
  successful mutation is recorded; an evicted version is unavailable rather
  than reconstructed.
- Fork copies source metadata exactly and does not add hidden provenance keys;
  hosts can put explicit provenance in their metadata if required.
- File schema evolution is read-compatible with the existing direct snapshot
  object and writes a versioned envelope only after a successful mutation or
  fork.

## Open questions (blocking — answered before G1)

- None for this local, provider-neutral contract. Hosted tenancy, encryption,
  distributed retention, and remote branch synchronization remain separate
  human-gated decisions.

**Human confirmed:** no — scope is an unblocked continuation slice selected
from the existing parity ledger; no material ambiguity requires human input.
