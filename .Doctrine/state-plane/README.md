# doctrine-state-plane

Makes any stateless coding model stateful inside a `.Doctrine` repo. The model never
remembers; the repo does. Three invariants:

1. **Externalized.** All state is plain canonical files under `.doctrine-state/`,
   committed to git. No vendor memory feature is load-bearing.
2. **Deterministic rehydration.** Same HEAD + same state plane → byte-identical
   hydration bundle. Rehydration is a compile step with a hash gate, not a vibe.
3. **Transactional sessions.** A session runs between checkpoints. Writes go through
   "model proposes, validator disposes" against schemas — memory cannot free-write
   itself into rot.

## Layout

```
doctrine-state-plane/
├── README.md                        ← you are here
├── STATE.md                         ← the spec: state kinds, layout, checkpoint protocol, defenses
├── schemas/
│   ├── checkpoint.schema.json       ← control plane + merkle-style index over the state plane
│   └── distillate.schema.json       ← what a session learned; hard caps mechanize "distill, never replay"
├── hydration/
│   └── HYDRATION.md                 ← assembly order, token budgets, determinism gate, adapter emit
└── examples/
    ├── checkpoint.example.json
    └── distillate.example.json
```

## How it composes with the other packs

Structure state is graphify's `graph.json` (already integrated; referenced by commit
hash, never owned here). Checkpoints hash-link like ContextChain. Effects follow
retrace's log discipline. Intents are RIR outputs. The bundle emits in ISON. FDE phase
gates are natural checkpoint triggers. AceIQ360 is the optional cross-repo tier above
this repo-local plane — imported claims arrive tagged with their source repo, never
merged silently.

## Adoption order

Start with checkpoint + distillate only (one file each, immediate value: sessions stop
re-exploring dead ends). Add the hydration compiler second. Wire adapter hooks last —
the state plane is useful even when hydration is a manual `@include`.
