# ADR-145: Bounded session history and branching

**Date:** 2026-08-29  
**Status:** accepted for the scoped local preview contract  
**Deciders:** Chief Architect

## Context

`SessionSnapshot.version` gives callers optimistic concurrency, but the built-in
stores retain only the current snapshot. A caller cannot inspect an earlier
version or branch a conversation before an append, clear, or host-supplied
compaction. The parity ledger therefore still reports the session surface as
partial despite having bounded JSON-safe messages and local persistence.

## Decision

We will extend the built-in session stores with bounded `history()` inspection
and `fork()` branching from a retained exact version. Each successful session
mutation records a detached snapshot in a count-bounded chronological history;
the newest retained `max_history` snapshots are kept, with a default of `100`
and a hard maximum of `10,000`. `history()` returns the newest bounded tail in
ascending version order. `fork()` validates the source and optional optimistic
version, copies the selected messages and metadata into a new session whose
version starts at `0`, and never executes or interprets stored content.

The file store will persist the current snapshot and history in one atomic
versioned JSON envelope. It will continue reading the existing direct
single-snapshot format as a one-entry history and will not rewrite that file
until a successful mutation or fork. The serialized envelope, including
history, remains subject to `max_session_bytes`; all failures occur before
replacement or in-memory map mutation.

## Alternatives considered

| Option | Pros | Cons | Why not |
|---|---|---|---|
| Atomic versioned envelope with bounded history (chosen) | One file replacement preserves current/history consistency; legacy reads are simple; no dependency | A session file grows with retained snapshots and old versions are eventually evicted | Fits the existing atomic JSON store and makes crash recovery inspectable without a second-file transaction |
| Separate `.history` sidecar | Keeps the current file small and can be added beside legacy data | Two files require a cross-file commit protocol and can disagree after a crash | Violates the local no-ambiguous-history boundary without introducing a more complex transaction protocol |
| Current-tip clone only | Tiny implementation and no schema change | Does not support time-travel or inspection of prior versions | Fails the parity gap this slice is intended to close |

## Data flow and failure boundary

```text
session mutation
      |
      v
validate + build detached candidate -- invalid/oversized --> typed error, no state change
      |
      v
append candidate to bounded history -- retention eviction --> oldest entry only
      |
      v
in-memory map OR atomic file envelope
      |
      +--> history(session_id, limit) --> detached chronological snapshots
      |
      +--> fork(source, target, version) -- stale/missing/conflict --> typed error
                                      |
                                      v
                           independent target at version 0
```

## Consequences

- Positive: local hosts can inspect and branch bounded conversation state for
  debugging and exploratory workflows; file restart preserves the same
  retained versions; source state remains immutable during a fork.
- Negative / debt accepted: history consumes session byte budget, evicts old
  versions by count, and does not merge branches or prove distributed
  consistency. A branch copies data but has no implicit parent lineage.
- Invalidation triggers: hosted/multi-tenant session storage, cross-process
  concurrent writers, encrypted history, age/cost retention, branch merge,
  distributed cursors, or automatic token-aware compaction would reopen this
  decision with a new storage and privacy design.
