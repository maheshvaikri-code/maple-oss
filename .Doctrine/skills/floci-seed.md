---
name: floci-seed
description: Load deterministic synthetic demo data into provisioned Floci services. Use this in FDE phase P4 after floci-provision, whenever seed data is missing or stale, or whenever the user asks to "load demo data", "populate", "seed", or "reset the data" for a prototype. Also use it when a demo produces different output hashes across runs — stale or nondeterministic seed data is the first suspect.
version: 0.1.0
inputs: [floci.manifest.yaml (seed block), .env.floci]
outputs: [data/seed-manifest.json]
---

# floci-seed

All demo data flows from one integer. Synthetic by default; real data is a guarded
exception, not a convenience.

## Procedure

1. Read the `seed` block from the manifest: the master `seed` integer and `datasets[]`
   (each: `kind`, `count`, generator params).
2. **Real-data guard.** If any dataset is non-synthetic: require
   `seed.real_data_cleared: true` AND a `provenance` note in the manifest. Absent either →
   stop and escalate. Never copy real files into the workspace "temporarily".
3. Generate each dataset with a PRNG derived as `seed ⊕ dataset_index` (stdlib PRNG,
   pinned algorithm — no third-party faker dependencies).
4. Load objects via the endpoints in `.env.floci` only.
5. Emit `data/seed-manifest.json` — canonical JSON mapping every seeded object to its
   sha256, plus `{seed, floci_version, manifest_sha256, total_objects}`.

## Idempotency gate

Tear down, re-provision, re-seed: the new seed-manifest must be byte-identical to the
old one. Hash inequality is a hard failure — find the nondeterminism (timestamps,
iteration order, uuids) and eliminate it; do not regenerate until it "settles".

## Failure modes

- **Endpoint unreachable:** stop; report which service — do not skip datasets.
- **Partial load:** delete all seeded objects for that dataset and retry the dataset
  once from scratch; a second failure stops the run.
- **Oversize dataset** (would exceed emulator quotas): stop and propose a reduced
  `count`; never silently truncate.
