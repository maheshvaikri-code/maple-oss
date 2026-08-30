---
integration: floci
upstream: https://github.com/floci-io/floci
license: MIT
discipline: local-cloud-emulation
verified: 2026-07-12
---

# floci — Integration

The local cloud emulator family the doctrine's cloud skills
(`skills/cloud-aws.md`, `cloud-azure.md`, `cloud-gcp.md`) and the FDE
pipeline build on. Verified real and maintained (2026-07-12):
[floci.io](https://floci.io) · [github.com/floci-io](https://github.com/floci-io).
MIT-licensed, open source, credential-free.

## What it is

- **floci** (AWS) — default port 4566 (LocalStack-compatible), built with
  Quarkus Native for fast startup.
- **floci-az** (Azure) — Blob, Queue, Table, Functions, App Config,
  Key Vault, Event Hubs, Service Bus (Azurite-compatible surface).
- **floci-gcp** (GCP) — GCS, Pub/Sub, Firestore, Cloud Run, Cloud SQL, GKE.
- **floci-cli** — one install starts/stops/inspects all three;
  **floci-ui** — a local console.

## Why floci as the default (and the fallbacks)

LocalStack began requiring an auth token in March 2026; floci is
credential-free by charter ("no auth tokens, no feature gates — ever"),
which matches the FDE zero-credential guardrail exactly. If floci is
unavailable in an environment, the per-cloud fallbacks are:

| Cloud | Fallback | Caveat |
|-------|----------|--------|
| AWS   | LocalStack | auth token required since 2026-03; port 4566 same |
| Azure | Azurite    | storage surface only — no Functions/Event Hubs |
| GCP   | gcloud emulators | per-service (`*_EMULATOR_HOST`), no unified CLI |

The cloud skills' rules (one client factory, `.env`-only endpoints,
hard-fail on missing emulator vars, parity ledger before promotion)
apply unchanged over any of these — only the endpoint URLs differ.

## Pin discipline

Pin the floci version in `floci.manifest.yaml` (`floci.version`);
`skills/floci-provision.md` hard-stops on CLI/manifest version drift
because the parity fidelity table is version-specific.
