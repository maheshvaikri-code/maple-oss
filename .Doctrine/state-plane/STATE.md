---
spec: doctrine-state-plane
version: 0.3.0
---

# STATE.md — the .Doctrine state plane

## Directory layout (in a target repo)

> Spec amendment (0.2.0): the state root is `.doctrine-state/`, not
> `.doctrine/state/`. On case-insensitive filesystems (Windows, macOS
> default) `.doctrine/` and `.Doctrine/` are the same directory, which
> would land runtime state inside the doctrine corpus and record paths a
> POSIX clone can't find. Found by the G5 QA pass of the reference
> implementation (`tools/doctrine_state.py`).

```
.doctrine-state/
├── checkpoint.json                  # current control state (schema: checkpoint)
├── checkpoints/                     # append-only history: <seq>-<shorthash>.json
├── intent/<task-id>.intent.json     # RIR outputs / task ledger
├── decisions/DECISIONS.ndjson       # append-only decision log (DLTG-lite)
├── effects/<session>.effects.ndjson # retrace-style side-effect log
├── distillates/<seq>-<hash>.json    # last N retained (default 5)
└── local/                           # machine-local scratch — the ONLY gitignored dir
```

Everything except `local/` is committed. State that doesn't survive a clone isn't state.

## State kinds

| Kind | Lives in | Writer | Lifetime | Staleness rule |
|---|---|---|---|---|
| Intent | `intent/` | RIR validator | until task closed | flagged if it references paths absent at HEAD |
| Structure | `graphify-out/graph.json` | graphify hook | per commit | stale when `built_at_commit != HEAD` |
| Decisions | `decisions/` | checkpoint protocol, append-only | permanent | never — it's history |
| Effects | `effects/` | retrace logger | until confirmed/compensated | unresolved entries surface at hydration |
| Distillate | `distillates/` | checkpoint protocol | last N (default 5) | superseded by newer; dead-ends merge forward |
| Control | `checkpoint.json` | checkpoint protocol | current | any `at_commit < HEAD` reference is flagged |

## Checkpoint protocol

**Triggers:** session end; every phase-gate pass (FDE P-gates); before any multi-file or
irreversible operation; explicit `/checkpoint`.

**Steps:**
1. **Propose.** The model drafts the checkpoint delta: control fields + one distillate,
   both as schema instances. Nothing else is writable.
2. **Dispose.** The validator checks both against the schemas (`additionalProperties:
   false` — unknown fields are rejected, not ignored), stamps `at_commit` from HEAD,
   and computes `prev_sha256` over the previous checkpoint's canonical bytes.
3. **Write.** `checkpoint.json` replaced; a copy appended to `checkpoints/`; distillate
   written; distillates beyond N pruned (their `dead_ends` merged forward, deduped, so
   hard-won negatives outlive the prune); decision entries appended if the distillate
   carries `decision_ref` claims.
4. **Commit.** `git commit -m "state: checkpoint <seq>"` (charter may route this to a
   staged-for-human policy instead).

**Verification.** `verify` walks `checkpoints/` confirming every `prev_sha256` link and
re-hashing the files named in `state_index`. One broken link = detected desync — the
chain property is ContextChain's, applied to session state.

## Canonicalization (pack-wide, same as sibling packs)

Hashed artifacts serialize as UTF-8, LF, lexicographically sorted keys, no trailing
whitespace, single trailing newline. NDJSON logs: one canonical object per line,
append-only, never rewritten.

## Failure-mode defenses

1. **Transcript-as-state** → distillate schema hard-caps entries and lengths; evidence
   fields are `file:line`, commands, or decision ids — never dialogue quotes. Hydration
   never includes raw transcript. Distill, never replay.
2. **Stale-as-fresh** → every artifact carries `at_commit`; the hydration compiler
   prefixes anything behind HEAD with `STALE@<commit>` and rebuilds structure state.
3. **Memory rot** → schema-only writes, validator disposes, unknown fields rejected.
4. **Chain desync** → `prev_sha256` links + `state_index` hashes; `verify` in CI.
5. **Cross-repo leakage** → the plane is repo-local; AceIQ360 imports are explicit and
   source-tagged, never silently merged.

## Concurrency (spec 0.3.0)

The chain is single-writer by design; concurrency is handled at two
distinct boundaries:

- **Same worktree — the lease.** `local/lease.json` (gitignored, never
  travels) records the writing session and a TTL (default 3600s).
  `checkpoint` refuses while another session's unexpired lease holds;
  `--steal` takes over deliberately and loudly. The lease guards chain
  APPEND only — prune stages material consumed by the next (guarded)
  checkpoint, and merge operates on a chain where the lease has already
  failed its job.
- **Across clones — fork detection + merge.** Two clones checkpointing
  independently reunite via git as duplicate seq files (same
  predecessor). `verify` reports `CHAIN FORKED` naming both heads, and
  `hydrate` refuses — a fork is a loud full stop, never silent
  divergence. `merge --loser <file>` resolves a LEAF fork: the losing
  head and its distillate are archived under `forks/` (history is never
  deleted), `checkpoint.json` repoints to the winning head, the loser's
  `dead_ends` are staged into the pending file the next checkpoint
  consumes (negatives survive the merge mechanically), and the loser's
  `learned`/`open_threads` are printed for honest re-proposal — claims
  are never auto-grafted onto a chain their session didn't verify.

## Epistemics

Distillate claims carry `confidence: verified | inferred` — same discipline as
graphify's `EXTRACTED | INFERRED` edges and the parity ledger's fidelity classes.
Derived claims are labeled derived, everywhere, with one vocabulary per artifact.
