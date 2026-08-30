# FDE / floci — integration overview

A `.Doctrine` role + skill pack: a **Forward-Deployed Engineer that carries its own cloud**.
The FDE turns a raw customer ask into a demo-ready, promotion-ready AI prototype without
touching a real cloud account — all infrastructure runs on Floci (local three-cloud emulator),
deterministically, at zero cost. Promotion to a real cloud is an emitted config diff, not a rebuild.

## Installed layout (merged into `.Doctrine/` at doctrine v0.1.3)

```
.Doctrine/
├── roles/fde.md                       ← the FDE role spec (mission, guardrails, 6-phase loop, gates)
├── rubrics/discovery.rubric.md        ← QUMBA RIR authority document for the discovery interview
├── skills/
│   ├── floci-provision.md             ← manifest → emulated infra + endpoints.lock.json + .env.floci
│   ├── floci-seed.md                  ← seeded synthetic data + hash-verified seed manifest
│   ├── floci-parity.md                ← the honesty layer: emits parity-ledger.json, gates promote
│   └── floci-promote.md               ← emit-only IaC diff + promotion checklist (never applies)
├── schemas/parity-ledger.schema.json  ← JSON Schema for the ledger; canonical-bytes hashing rules
└── examples/floci.manifest.yaml       ← worked manifest for the rag-over-docs archetype
```

## Phase → skill → artifact map

| Phase | Skill | Gate artifact |
|---|---|---|
| P1 Discover | qumba-rir + `discovery.rubric.md` | `intent-spec.json` (human sign-off) |
| P2 Shape | (role logic) | `floci.manifest.yaml` (schema-valid) |
| P3 Provision | floci-provision | `endpoints.lock.json` (health green, hash-stable) |
| P4 Build | (role logic) | `make demo` ×2 from clean → identical output hash |
| P5 Verify | floci-parity (+ ReplayLens if retrieval) | `parity-ledger.json` (gate ≠ block) |
| P6 Promote | floci-promote | `iac-diff/` + `PROMOTION.md` (human sign-off) |

## The one invariant

**Emulator-verified is never presented as cloud-verified.** Every prototype ships with a
parity ledger classifying each cloud API call it exercised as `high | partial | stub |
unsupported` fidelity. `floci-promote` refuses to run without a ledger, and blocks if any
critical-path call is `stub` or `unsupported`. The ledger — not the demo — is what makes
the promotion step trustworthy.

## Install & bind

1. Role and skills are already merged into this `.Doctrine/` tree (see layout above);
   the Routing Table in `.Doctrine.md` §6 routes prototype/demo asks to them.
2. **Bind CLI names**: skill procedures assume `floci up | down | status | logs`. Align these
   with your installed Floci version and pin that version in the manifest (`floci.version`).
3. Adapters: the role spec is agent-agnostic (plain shell + file ops, no tool-specific syntax),
   so existing `.Doctrine` adapters (Codex, Cursor, Windsurf, Copilot, …) carry it unchanged.

## Determinism conventions (pack-wide)

Canonical JSON everywhere an artifact is hashed: UTF-8, LF line endings, keys sorted
lexicographically, no trailing whitespace, single trailing newline. All randomness flows
from the single `seed` integer in the manifest. Ports are fixed and declared, never ephemeral.
Idempotency is proven by hash equality, not by eyeballing.
